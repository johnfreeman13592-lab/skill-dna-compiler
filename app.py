from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import streamlit as st
from pydantic import SecretStr, ValidationError

from skill_dna_compiler import __release_label__
from skill_dna_compiler.config.settings import get_settings
from skill_dna_compiler.credentials import CredentialStoreError, KeyringCredentialStore
from skill_dna_compiler.domain import (
    CandidateStatus,
    InstructionTrace,
    SkillUsageStatus,
    SkillUsefulness,
    TraceReviewStatus,
)
from skill_dna_compiler.exporting import SkillExportService
from skill_dna_compiler.extraction import (
    ExtractionProviderError,
    PayloadLimitError,
    PreparedPayload,
    prepare_extraction_payload,
)
from skill_dna_compiler.extraction.costs import (
    PRICING_REVIEWED_ON,
    PricingUnavailableError,
    calculate_actual_token_cost,
    estimate_extraction_cost,
)
from skill_dna_compiler.extraction.mock_provider import (
    StaticMockExtractionProvider,
    build_demo_extraction_result,
)
from skill_dna_compiler.extraction.openai_provider import (
    PROMPT_VERSION,
    OpenAIExtractionProvider,
)
from skill_dna_compiler.extraction.schemas import ExtractedCandidate, ExtractionResult
from skill_dna_compiler.extraction.service import ExtractionService
from skill_dna_compiler.logging_config import configure_logging
from skill_dna_compiler.review import (
    enumerate_traceable_instructions,
    find_duplicate_candidates,
    merge_candidate_data,
    reconcile_instruction_traces,
    source_reference_fingerprint,
    trace_gate_errors,
)
from skill_dna_compiler.skill_dna import SkillDNAService
from skill_dna_compiler.storage.database import Database
from skill_dna_compiler.storage.repositories import (
    ExportRepository,
    ExtractionRepository,
    SavedCandidate,
    SkillDNARepository,
    SkillFeedbackRepository,
    VaultRepository,
)
from skill_dna_compiler.ui import (
    DEFAULT_LANGUAGE,
    LANGUAGE_LABELS,
    MAX_FEEDBACK_FIELD_CHARS,
    Language,
    build_first_use_feedback_report,
    build_guided_walkthrough_data_uri,
    inject_theme,
    render_local_safety_sidebar,
    text,
)
from skill_dna_compiler.vault import (
    MarkdownParseError,
    VaultFile,
    VaultScanError,
    parse_markdown_file,
    scan_vault,
)


def _language() -> Language:
    value = st.session_state.get("ui_language", DEFAULT_LANGUAGE)
    return value if value in LANGUAGE_LABELS else DEFAULT_LANGUAGE


def _t(key: str, **values: object) -> str:
    return text(_language(), key, **values)


class GuidedView(StrEnum):
    HOME = "home"
    NOTES = "notes"
    DATA = "data"
    REVIEW = "review"
    SAVE = "save"
    SETTINGS = "settings"


class GuidedJourneySource(StrEnum):
    EXTRACTION = "extraction"
    HISTORY = "history"


@dataclass(frozen=True)
class GuidedEligibility:
    notes_selected: bool = False
    draft_available: bool = False
    approved_candidate: bool = False


_GUIDED_STEPS = (
    GuidedView.NOTES,
    GuidedView.DATA,
    GuidedView.REVIEW,
    GuidedView.SAVE,
)


def guided_view_is_eligible(
    view: GuidedView,
    eligibility: GuidedEligibility,
) -> bool:
    """Return whether the current repository/session facts allow one view."""

    if view in {GuidedView.HOME, GuidedView.NOTES, GuidedView.SETTINGS}:
        return True
    if view is GuidedView.DATA:
        return eligibility.notes_selected
    if view is GuidedView.REVIEW:
        return eligibility.draft_available
    return eligibility.approved_candidate


def resolve_guided_view(
    requested: str | GuidedView,
    eligibility: GuidedEligibility,
) -> GuidedView:
    """Fail stale or malformed navigation back to the nearest safe view."""

    try:
        view = GuidedView(requested)
    except ValueError:
        return GuidedView.HOME
    if guided_view_is_eligible(view, eligibility):
        return view
    if view not in _GUIDED_STEPS:
        return GuidedView.HOME
    requested_index = _GUIDED_STEPS.index(view)
    for fallback in reversed(_GUIDED_STEPS[:requested_index]):
        if guided_view_is_eligible(fallback, eligibility):
            return fallback
    return GuidedView.NOTES


def note_selection_is_current(
    files: list[VaultFile],
    selected_paths: list[str],
    vault_id: object | None,
) -> bool:
    """Treat widget state as current only while it belongs to the loaded Vault."""

    available = {item.relative_path for item in files}
    return bool(vault_id and selected_paths and set(selected_paths).issubset(available))


_CURRENT_JOURNEY_KEYS = (
    "current_journey_source",
    "current_run_id",
    "current_candidate_ids",
    "current_approved_candidate_id",
    "current_payload_fingerprint",
    "current_provider_kind",
    "current_provider_model",
    "current_prompt_version",
    "history_resume_candidate_id",
)
_DOWNSTREAM_CONFIRMATION_PREFIXES = (
    "confirm_skill_dna_",
    "confirm_export_preview_",
    "confirm_export_overwrite_",
)


def prepared_payload_fingerprint(prepared: PreparedPayload) -> str:
    """Return a non-secret identity for the exact redacted payload."""

    return hashlib.sha256(prepared.serialized_json.encode("utf-8")).hexdigest()


def _clear_session_prefixes(prefixes: tuple[str, ...]) -> None:
    for key in list(st.session_state):
        if key.startswith(prefixes):
            st.session_state.pop(key, None)


def _invalidate_current_approval() -> None:
    st.session_state.pop("current_approved_candidate_id", None)
    st.session_state.pop("skill_dna_candidate_id", None)
    st.session_state.pop("export_skill_dna_id", None)
    _clear_session_prefixes(_DOWNSTREAM_CONFIRMATION_PREFIXES)


def _invalidate_current_journey(*, clear_prepared: bool) -> None:
    for key in _CURRENT_JOURNEY_KEYS:
        st.session_state.pop(key, None)
    for key in (
        "extraction_result",
        "extraction_provider_kind",
        "actual_api_usage",
        "review_candidate_id",
        "duplicate_pair",
        "merge_primary_candidate",
    ):
        st.session_state.pop(key, None)
    _invalidate_current_approval()
    if clear_prepared:
        for key in (
            "prepared_payload",
            "prepared_selection",
            "payload_confirmed",
            "cost_confirmed",
        ):
            st.session_state.pop(key, None)


def _record_current_extraction(
    repository: ExtractionRepository,
    *,
    run_id: str,
    prepared: PreparedPayload,
    provider_kind: str,
    model: str,
    prompt_version: str,
) -> None:
    candidate_ids = [
        item.id
        for item in repository.list_candidates()
        if item.extraction_run_id == run_id
    ]
    st.session_state.update(
        {
            "current_journey_source": GuidedJourneySource.EXTRACTION.value,
            "current_run_id": run_id,
            "current_candidate_ids": candidate_ids,
            "current_payload_fingerprint": prepared_payload_fingerprint(prepared),
            "current_provider_kind": provider_kind,
            "current_provider_model": model,
            "current_prompt_version": prompt_version,
        }
    )
    _invalidate_current_approval()


def _record_history_resume(candidate_id: str, extraction_run_id: str) -> None:
    _invalidate_current_journey(clear_prepared=False)
    st.session_state.update(
        {
            "current_journey_source": GuidedJourneySource.HISTORY.value,
            "current_run_id": extraction_run_id,
            "current_candidate_ids": [candidate_id],
            "history_resume_candidate_id": candidate_id,
        }
    )
    _set_guided_view(GuidedView.REVIEW)


def _current_journey_candidates(
    repository: ExtractionRepository,
) -> list[SavedCandidate]:
    raw_ids = st.session_state.get("current_candidate_ids", [])
    if not isinstance(raw_ids, list) or not raw_ids:
        return []
    candidate_ids = [value for value in raw_ids if isinstance(value, str)]
    if len(candidate_ids) != len(raw_ids):
        return []
    candidates_by_id = {
        item.id: item
        for item in repository.list_candidates()
        if item.id in candidate_ids
    }
    if set(candidates_by_id) != set(candidate_ids):
        return []
    candidates = [candidates_by_id[candidate_id] for candidate_id in candidate_ids]
    run_id = st.session_state.get("current_run_id")
    if not run_id or any(item.extraction_run_id != run_id for item in candidates):
        return []
    source = st.session_state.get("current_journey_source")
    if source == GuidedJourneySource.HISTORY.value:
        resumed_id = st.session_state.get("history_resume_candidate_id")
        return candidates if candidate_ids == [resumed_id] else []
    if source != GuidedJourneySource.EXTRACTION.value:
        return []
    prepared = st.session_state.get("prepared_payload")
    if not isinstance(prepared, PreparedPayload):
        return []
    if st.session_state.get("current_payload_fingerprint") != prepared_payload_fingerprint(
        prepared
    ):
        return []
    if (
        st.session_state.get("current_provider_kind")
        != st.session_state.get("extraction_provider_kind")
        or not st.session_state.get("current_provider_model")
        or not st.session_state.get("current_prompt_version")
    ):
        return []
    return candidates


def _sync_runtime_extraction_config(
    model: str,
    reasoning_effort: str,
    max_output_tokens: int,
) -> None:
    signature = (model, reasoning_effort, max_output_tokens)
    previous = st.session_state.get("guided_runtime_extraction_config")
    if previous is not None and previous != signature:
        _invalidate_current_journey(clear_prepared=False)
        st.session_state.pop("payload_confirmed", None)
        st.session_state.pop("cost_confirmed", None)
    st.session_state["guided_runtime_extraction_config"] = signature


def _bundled_sample_vault() -> Path | None:
    override = os.environ.get("SKILL_DNA_SAMPLE_VAULT_PATH")
    if override:
        candidate = Path(override)
    elif getattr(sys, "frozen", False):
        candidate = Path(sys.executable).resolve().parent / "Sample Vault"
    else:
        candidate = Path(__file__).resolve().parent / "tests" / "fixtures" / "sample_vault"
    resolved = candidate.resolve()
    return resolved if resolved.is_dir() else None


def _render_first_use_feedback() -> None:
    with st.expander(_t("first_feedback.title"), expanded=False):
        st.caption(_t("first_feedback.caption"))
        outcome_labels = {
            value: _t(f"first_feedback.outcome.{value}")
            for value in ("exploring", "completed", "stopped")
        }
        outcome = st.selectbox(
            _t("first_feedback.outcome"),
            list(outcome_labels),
            format_func=outcome_labels.get,
            key="first_feedback_outcome",
        )
        step_labels = {
            value: _t(f"first_feedback.step.{value}")
            for value in (
                "opened",
                "sample",
                "mock",
                "evidence",
                "approval",
                "export",
            )
        }
        furthest_step = st.selectbox(
            _t("first_feedback.step"),
            list(step_labels),
            format_func=step_labels.get,
            key="first_feedback_step",
        )
        difficulty_labels = {
            value: _t(f"first_feedback.difficulty.{value}")
            for value in (
                "none",
                "trust",
                "purpose",
                "launch",
                "sample",
                "extraction",
                "evidence",
                "approval_export",
                "error_other",
            )
        }
        main_difficulty = st.selectbox(
            _t("first_feedback.difficulty"),
            list(difficulty_labels),
            format_func=difficulty_labels.get,
            key="first_feedback_difficulty",
        )
        reuse_labels = {
            value: _t(f"first_feedback.reuse.{value}")
            for value in ("unsure", "yes", "maybe", "no")
        }
        reuse_intent = st.selectbox(
            _t("first_feedback.reuse"),
            list(reuse_labels),
            format_func=reuse_labels.get,
            key="first_feedback_reuse",
        )
        worked_well = st.text_area(
            _t("first_feedback.worked"),
            max_chars=MAX_FEEDBACK_FIELD_CHARS,
            key="first_feedback_worked",
        )
        blocked_or_unclear = st.text_area(
            _t("first_feedback.blocked"),
            max_chars=MAX_FEEDBACK_FIELD_CHARS,
            key="first_feedback_blocked",
        )
        repeated_correction = st.text_area(
            _t("first_feedback.repeated"),
            max_chars=MAX_FEEDBACK_FIELD_CHARS,
            key="first_feedback_repeated",
        )
        st.warning(_t("first_feedback.safety"))

        language = _language()
        report = build_first_use_feedback_report(
            release_label=__release_label__,
            language=language,
            language_label=LANGUAGE_LABELS[language],
            outcome=outcome_labels[outcome],
            furthest_step=step_labels[furthest_step],
            main_difficulty=difficulty_labels[main_difficulty],
            reuse_intent=reuse_labels[reuse_intent],
            worked_well=worked_well,
            blocked_or_unclear=blocked_or_unclear,
            repeated_correction=repeated_correction,
        )
        if report.findings:
            st.warning(
                _t(
                    "first_feedback.redacted",
                    count=len(report.findings),
                )
            )
        st.markdown(f"**{_t('first_feedback.preview')}**")
        st.code(report.markdown, language="markdown", wrap_lines=True)

        signature = hashlib.sha256(report.markdown.encode("utf-8")).hexdigest()
        if st.session_state.get("first_feedback_signature") != signature:
            st.session_state["first_feedback_signature"] = signature
            st.session_state["first_feedback_confirmed"] = False
        confirmed = st.checkbox(
            _t("first_feedback.confirm"),
            key="first_feedback_confirmed",
        )
        st.download_button(
            _t("first_feedback.download"),
            data=report.markdown.encode("utf-8"),
            file_name=f"skill-dna-compiler-{__release_label__}-first-use-feedback.md",
            mime="text/markdown",
            disabled=not confirmed,
            key="download_first_feedback",
        )
        st.caption(_t("first_feedback.manual"))


def _render_extraction_result(
    result: ExtractionResult,
    prepared: PreparedPayload,
    *,
    provider_label: str,
) -> None:
    st.success(
        _t(
            "extract.completed",
            provider=provider_label,
            count=len(result.candidates),
        )
    )
    if not result.candidates:
        st.info(_t("extract.no_candidates"))
        return

    documents = {item.document_id: item for item in prepared.payload.documents}
    st.markdown(_t("extract.verified_candidates"))
    st.caption(_t("extract.not_approved"))
    for index, candidate in enumerate(result.candidates, start=1):
        with st.expander(
            _t(
                "extract.confidence",
                index=index,
                name=candidate.name,
                confidence=candidate.confidence,
            )
        ):
            st.write(candidate.description)
            st.write(
                _t(
                    "extract.category",
                    category=candidate.category,
                    generality=candidate.generality,
                )
            )
            st.write(_t("extract.confidence_reason", reason=candidate.confidence_reason))
            if candidate.triggers:
                st.markdown(_t("extract.triggers"))
                for trigger in candidate.triggers:
                    st.markdown(f"- {trigger}")
            if candidate.workflow:
                st.markdown(_t("extract.workflow"))
                for step in candidate.workflow:
                    st.markdown(f"{step.order}. {step.action}")
            st.markdown(_t("extract.sources"))
            for reference in candidate.source_references:
                document = documents[reference.document_id]
                st.caption(f"{document.title} — {document.path}")
                st.code(reference.quote, language=None, wrap_lines=True)
                st.write(reference.reason)
            if candidate.warnings:
                st.warning(" / ".join(candidate.warnings))


def _render_extraction_preview(
    files: list[VaultFile],
    selected_paths: list[str],
    max_input_chars: int,
    extraction_service: ExtractionService,
    candidate_repository: ExtractionRepository,
    openai_api_key: SecretStr | None,
    openai_model: str,
    reasoning_effort: str,
    max_output_tokens: int,
    document_ids_by_path: dict[str, str],
) -> None:
    st.subheader(_t("payload.title"))
    st.caption(_t("payload.caption"))

    selection_signature = tuple(selected_paths)
    if st.session_state.get("prepared_selection") != selection_signature:
        _invalidate_current_journey(clear_prepared=True)

    if not selected_paths:
        st.info(_t("payload.select_note"))
        return

    if st.button(_t("payload.prepare")):
        selected_files = [item for item in files if item.relative_path in selected_paths]
        try:
            notes = [parse_markdown_file(item) for item in selected_files]
            prepared = prepare_extraction_payload(
                notes,
                max_characters=max_input_chars,
                document_ids_by_path=document_ids_by_path,
            )
        except (MarkdownParseError, PayloadLimitError, ValueError) as exc:
            _invalidate_current_journey(clear_prepared=True)
            st.error(str(exc))
        else:
            _invalidate_current_journey(clear_prepared=False)
            st.session_state["prepared_payload"] = prepared
            st.session_state["prepared_selection"] = selection_signature
            st.session_state.pop("payload_confirmed", None)
            st.session_state.pop("cost_confirmed", None)

    prepared: PreparedPayload | None = st.session_state.get("prepared_payload")
    if prepared is None:
        return

    st.write(
        _t(
            "payload.summary",
            documents=len(prepared.payload.documents),
            characters=prepared.character_count,
            redactions=prepared.payload.redaction_count,
        )
    )
    if prepared.findings:
        st.warning(_t("payload.redacted_warning"))
        st.dataframe(
            [
                {
                    _t("vault.table_file"): item.document_path,
                    _t("payload.table_location"): item.location,
                    _t("payload.table_line"): item.finding.line,
                    _t("payload.table_kind"): item.finding.kind,
                    _t("payload.table_severity"): item.finding.severity.value,
                    _t("payload.table_replacement"): item.finding.replacement,
                }
                for item in prepared.findings
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.success(_t("payload.no_findings"))

    st.markdown(_t("payload.json_title"))
    st.code(prepared.serialized_json, language="json", wrap_lines=True)

    estimate = None
    try:
        estimate = estimate_extraction_cost(
            prepared.payload,
            model=openai_model,
            max_output_tokens=max_output_tokens,
        )
    except PricingUnavailableError:
        st.error(_t("cost.unavailable"))
    else:
        st.markdown(_t("cost.title"))
        st.write(_t("cost.model", model=estimate.model, effort=reasoning_effort))
        st.write(
            _t(
                "cost.tokens",
                low=estimate.input_tokens_low,
                high=estimate.input_tokens_high,
                maximum=estimate.max_output_tokens,
            )
        )
        st.write(
            _t(
                "cost.amount",
                low=estimate.input_cost_low_usd,
                high=estimate.input_cost_high_usd,
                maximum=estimate.maximum_total_usd,
            )
        )
        st.caption(_t("cost.review_date", date=PRICING_REVIEWED_ON))
        st.link_button(
            _t("cost.official_link"),
            "https://developers.openai.com/api/docs/pricing",
        )
        if estimate.long_context_pricing_possible:
            st.warning(_t("cost.long_context"))

    confirmed = st.checkbox(
        _t("payload.confirm"),
        key="payload_confirmed",
    )
    if st.button(_t("extract.mock"), disabled=not confirmed):
        _invalidate_current_journey(clear_prepared=False)
        try:
            run_id, result = extraction_service.run_with_id(
                payload=prepared.payload,
                provider=StaticMockExtractionProvider(
                    build_demo_extraction_result(
                        prepared.payload,
                        language=_language(),
                    )
                ),
                model="mock-local",
                prompt_version="static-mock-v1",
            )
        except ExtractionProviderError as exc:
            st.error(exc.user_message)
            if exc.retryable:
                st.caption(_t("extract.retry_mock"))
        else:
            st.session_state["extraction_result"] = result
            st.session_state["extraction_provider_kind"] = "mock"
            _record_current_extraction(
                candidate_repository,
                run_id=run_id,
                prepared=prepared,
                provider_kind="mock",
                model="mock-local",
                prompt_version="static-mock-v1",
            )

    if openai_api_key is None:
        st.warning(_t("extract.api_missing"))
    if st.session_state.pop("reset_live_confirmation", False):
        st.session_state["cost_confirmed"] = False
    cost_confirmed = st.checkbox(
        _t("extract.cost_confirm"),
        key="cost_confirmed",
    )
    live_disabled = (
        not confirmed or not cost_confirmed or openai_api_key is None or estimate is None
    )
    if st.button(
        _t("extract.live"),
        type="primary",
        disabled=live_disabled,
    ):
        assert openai_api_key is not None
        st.session_state["reset_live_confirmation"] = True
        _invalidate_current_journey(clear_prepared=False)
        provider = OpenAIExtractionProvider.from_api_key(
            api_key=openai_api_key,
            model=openai_model,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
        )
        try:
            with st.spinner(_t("extract.spinner")):
                run_id, result = extraction_service.run_with_id(
                    payload=prepared.payload,
                    provider=provider,
                    model=openai_model,
                    prompt_version=PROMPT_VERSION,
                )
        except ExtractionProviderError as exc:
            st.error(exc.user_message)
            if exc.retryable:
                st.caption(_t("extract.retry_live"))
        else:
            st.session_state["extraction_result"] = result
            st.session_state["extraction_provider_kind"] = "openai"
            _record_current_extraction(
                candidate_repository,
                run_id=run_id,
                prepared=prepared,
                provider_kind="openai",
                model=openai_model,
                prompt_version=PROMPT_VERSION,
            )
            if provider.last_usage is not None:
                actual_cost = calculate_actual_token_cost(
                    model=openai_model,
                    input_tokens=provider.last_usage.input_tokens,
                    output_tokens=provider.last_usage.output_tokens,
                )
                st.session_state["actual_api_usage"] = {
                    "input_tokens": provider.last_usage.input_tokens,
                    "output_tokens": provider.last_usage.output_tokens,
                    "total_tokens": provider.last_usage.total_tokens,
                    "cost_usd": str(actual_cost),
                }

    result: ExtractionResult | None = st.session_state.get("extraction_result")
    if result is not None:
        provider_kind = st.session_state.get("extraction_provider_kind", "generic")
        provider_label = _t(
            {
                "mock": "extract.mock_label",
                "openai": "extract.live_label",
                "generic": "extract.generic_label",
            }.get(provider_kind, "extract.generic_label")
        )
        _render_extraction_result(result, prepared, provider_label=provider_label)
        actual_usage = st.session_state.get("actual_api_usage")
        if provider_kind == "openai" and actual_usage is not None:
            st.info(
                _t(
                    "extract.actual_usage",
                    input=actual_usage["input_tokens"],
                    output=actual_usage["output_tokens"],
                    total=actual_usage["total_tokens"],
                    cost=actual_usage["cost_usd"],
                )
            )
        if provider_kind == "mock":
            st.caption(_t("extract.mock_free"))


def _render_vault_browser(
    repository: VaultRepository,
    extraction_service: ExtractionService,
    candidate_repository: ExtractionRepository,
    max_input_chars: int,
    openai_api_key: SecretStr | None,
    openai_model: str,
    reasoning_effort: str,
    max_output_tokens: int,
    *,
    show_payload: bool = True,
) -> None:
    st.subheader(_t("vault.title"))
    st.caption(_t("vault.caption"))
    saved_vault = repository.latest()
    sample_vault = _bundled_sample_vault()

    def use_sample_vault() -> None:
        assert sample_vault is not None
        st.session_state["vault_path_input"] = str(sample_vault)
        st.session_state["sample_vault_notice"] = True

    if "vault_path_input" not in st.session_state:
        st.session_state["vault_path_input"] = saved_vault.root_path if saved_vault else ""
    vault_path = st.text_input(
        _t("vault.path"),
        placeholder=r"C:\Users\name\Documents\My Vault",
        key="vault_path_input",
    )
    exclusions = st.text_input(
        _t("vault.exclusions"),
        value=(
            ",".join(saved_vault.exclude_paths)
            if saved_vault
            else ".obsidian,.git,.trash,node_modules"
        ),
    )
    if sample_vault is not None:
        st.button(_t("vault.use_sample"), on_click=use_sample_vault)
    if st.session_state.pop("sample_vault_notice", False):
        st.info(_t("vault.sample_ready"))

    if st.button(_t("vault.load"), type="primary"):
        if not vault_path.strip():
            st.warning(_t("vault.path_required"))
            return
        excluded_paths = tuple(item.strip() for item in exclusions.split(",") if item.strip())
        try:
            files = scan_vault(Path(vault_path.strip()), exclude_paths=excluded_paths)
            vault_id = repository.save_scan(Path(vault_path.strip()), excluded_paths, files)
            _invalidate_current_journey(clear_prepared=True)
            st.session_state["vault_id"] = vault_id
            st.session_state["vault_files"] = files
            st.session_state.pop("vault_error", None)
            for key in (
                "selected_note_paths",
                "selected_note_paths_widget",
                "vault_folder_filter",
                "vault_note_preview",
            ):
                st.session_state.pop(key, None)
        except VaultScanError as exc:
            st.session_state["vault_files"] = []
            st.session_state["vault_error"] = str(exc)

    if error := st.session_state.get("vault_error"):
        st.error(error)

    files: list[VaultFile] = st.session_state.get("vault_files", [])
    if not files:
        return

    st.success(_t("vault.loaded", count=len(files)))
    folders = sorted({str(Path(item.relative_path).parent).replace("\\", "/") for item in files})
    all_folders = _t("vault.all")
    selected_folder = st.selectbox(
        _t("vault.folder_filter"),
        options=[all_folders, *folders],
        key="vault_folder_filter",
    )
    search_text = st.text_input(_t("vault.search")).strip().casefold()
    filtered = [
        item
        for item in files
        if not search_text
        or search_text in item.title.casefold()
        or search_text in item.relative_path.casefold()
        if selected_folder == all_folders
        or str(Path(item.relative_path).parent).replace("\\", "/") == selected_folder
    ]

    st.dataframe(
        [
            {
                _t("vault.table_file"): item.title,
                _t("vault.table_path"): item.relative_path,
                _t("vault.table_size"): item.size_bytes,
                _t("vault.table_modified"): item.modified_at.isoformat(timespec="seconds"),
            }
            for item in filtered
        ],
        width="stretch",
        hide_index=True,
    )
    if not filtered:
        st.warning(_t("vault.no_matches"))
        return

    selectable_paths = [item.relative_path for item in filtered]
    if "selected_note_paths_widget" not in st.session_state:
        st.session_state["selected_note_paths_widget"] = [
            path
            for path in st.session_state.get("selected_note_paths", [])
            if path in selectable_paths
        ]
    selected_paths = st.multiselect(
        _t("vault.analysis_selection"),
        options=selectable_paths,
        key="selected_note_paths_widget",
    )
    if list(selected_paths) != st.session_state.get("selected_note_paths", []):
        _invalidate_current_journey(clear_prepared=True)
    st.session_state["selected_note_paths"] = list(selected_paths)
    vault_id = st.session_state.get("vault_id")
    try:
        document_ids_by_path = (
            repository.document_ids_for_paths(vault_id, selected_paths)
            if vault_id and selected_paths
            else {}
        )
    except ValueError as exc:
        st.error(str(exc))
        return

    selected_path = st.selectbox(
        _t("vault.preview"),
        options=[item.relative_path for item in filtered],
        key="vault_note_preview",
    )
    selected = next(item for item in filtered if item.relative_path == selected_path)
    try:
        parsed = parse_markdown_file(selected)
    except MarkdownParseError as exc:
        st.error(str(exc))
        return

    if parsed.frontmatter:
        with st.expander("Frontmatter"):
            st.json(parsed.frontmatter)
    st.code(parsed.body, language="markdown", wrap_lines=True)
    if show_payload:
        st.divider()
        _render_extraction_preview(
            files,
            selected_paths,
            max_input_chars,
            extraction_service,
            candidate_repository,
            openai_api_key,
            openai_model,
            reasoning_effort,
            max_output_tokens,
            document_ids_by_path,
        )


def _render_current_payload(
    repository: VaultRepository,
    extraction_service: ExtractionService,
    candidate_repository: ExtractionRepository,
    max_input_chars: int,
    openai_api_key: SecretStr | None,
    openai_model: str,
    reasoning_effort: str,
    max_output_tokens: int,
) -> None:
    files: list[VaultFile] = st.session_state.get("vault_files", [])
    selected_paths: list[str] = st.session_state.get("selected_note_paths", [])
    vault_id = st.session_state.get("vault_id")
    if not note_selection_is_current(files, selected_paths, vault_id):
        st.warning(_t("guided.block.notes"))
        return
    try:
        document_ids_by_path = repository.document_ids_for_paths(vault_id, selected_paths)
    except ValueError as exc:
        st.error(str(exc))
        return
    _render_extraction_preview(
        files,
        selected_paths,
        max_input_chars,
        extraction_service,
        candidate_repository,
        openai_api_key,
        openai_model,
        reasoning_effort,
        max_output_tokens,
        document_ids_by_path,
    )


def _split_review_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _render_instruction_trace_review(repository: ExtractionRepository, saved) -> list[str]:
    candidate = saved.candidate
    instructions = enumerate_traceable_instructions(candidate)
    traces = reconcile_instruction_traces(candidate, saved.instruction_traces)
    traces_by_key = {trace.instruction_key: trace for trace in traces}
    instruction_by_key = {item.key: item for item in instructions}
    approved_count = sum(trace.review_status is TraceReviewStatus.APPROVED for trace in traces)
    st.markdown(_t("trace.title"))
    st.caption(
        _t(
            "trace.summary",
            approved=approved_count,
            total=len(traces),
        )
    )
    st.progress(
        approved_count / len(traces),
        text=_t("trace.progress", approved=approved_count, total=len(traces)),
    )
    with st.expander(
        _t("trace.instructions_label"),
        expanded=approved_count == 0,
    ):
        st.markdown(_t("trace.instructions"))

    def instruction_label(key: str) -> str:
        trace = traces_by_key[key]
        status = {
            TraceReviewStatus.PENDING: _t("status.pending"),
            TraceReviewStatus.APPROVED: _t("status.approved"),
            TraceReviewStatus.REJECTED: _t("status.rejected"),
        }[trace.review_status]
        return f"[{status}] {key} — {instruction_by_key[key].text}"

    selected_key = st.selectbox(
        _t("trace.select_instruction"),
        [item.key for item in instructions],
        format_func=instruction_label,
        key=f"trace_instruction_{saved.id}",
    )
    selected = traces_by_key[selected_key]
    source_options = {
        source_reference_fingerprint(source): source for source in candidate.source_references
    }
    with st.form(f"trace_review_{saved.id}_{selected_key}"):
        st.code(instruction_by_key[selected_key].text, language=None, wrap_lines=True)
        selected_sources = st.multiselect(
            _t("trace.direct_sources"),
            list(source_options),
            default=[
                fingerprint
                for fingerprint in selected.source_reference_fingerprints
                if fingerprint in source_options
            ],
            format_func=lambda fingerprint: (
                f"{source_options[fingerprint].document_id}: "
                f"{source_options[fingerprint].quote[:80]}"
            ),
        )
        traceability = st.selectbox(
            _t("trace.traceability"),
            [0, 1, 2],
            index=selected.traceability,
            format_func=lambda value: {
                0: _t("trace.no_evidence"),
                1: _t("trace.related_evidence"),
                2: _t("trace.direct_evidence"),
            }[value],
            help=_t("trace.traceability_help"),
        )
        fidelity = st.selectbox(
            _t("trace.fidelity"),
            [0, 1, 2],
            index=selected.fidelity,
            format_func=lambda value: {
                0: _t("trace.fidelity_none"),
                1: _t("trace.fidelity_partial"),
                2: _t("trace.fidelity_full"),
            }[value],
            help=_t("trace.fidelity_help"),
        )
        impact_options: list[bool | None] = [None, False, True]
        high_impact = st.selectbox(
            _t("trace.impact"),
            impact_options,
            index=impact_options.index(selected.high_impact),
            format_func=lambda value: {
                None: _t("trace.impact_unknown"),
                False: _t("trace.impact_normal"),
                True: _t("trace.impact_high"),
            }[value],
            help=_t("trace.impact_help"),
        )
        boundary_options: list[int | None] = [None, 0, 1, 2]
        boundary = st.selectbox(
            _t("trace.boundary"),
            boundary_options,
            index=boundary_options.index(selected.boundary),
            format_func=lambda value: {
                None: _t("trace.boundary_unknown"),
                0: _t("trace.boundary_missing"),
                1: _t("trace.boundary_partial"),
                2: _t("trace.boundary_full"),
            }[value],
            help=_t("trace.boundary_help"),
        )
        decision = st.selectbox(
            _t("trace.decision"),
            list(TraceReviewStatus),
            index=list(TraceReviewStatus).index(selected.review_status),
            format_func=lambda value: {
                TraceReviewStatus.PENDING: _t("status.hold"),
                TraceReviewStatus.APPROVED: _t("status.approved"),
                TraceReviewStatus.REJECTED: _t("status.rejected"),
            }[value],
        )
        reviewer_note = st.text_input(
            _t("trace.note"),
            value=selected.reviewer_note,
        )
        save_trace = st.form_submit_button(_t("trace.save"))
    with st.expander(_t("trace.terms_label"), expanded=False):
        st.markdown(_t("trace.terms"))
    if save_trace:
        try:
            trace = InstructionTrace(
                instruction_key=selected_key,
                instruction_hash=instruction_by_key[selected_key].instruction_hash,
                source_reference_fingerprints=selected_sources,
                review_status=decision,
                traceability=traceability,
                fidelity=fidelity,
                boundary=boundary,
                high_impact=high_impact,
                reviewer_note=reviewer_note.strip(),
                reviewed_at=(
                    datetime.now(UTC) if decision is not TraceReviewStatus.PENDING else None
                ),
            )
            repository.save_instruction_trace(saved.id, trace)
        except (ValidationError, ValueError) as exc:
            st.error(_t("trace.save_failed", error=exc))
        else:
            if saved.id in st.session_state.get("current_candidate_ids", []):
                _invalidate_current_approval()
            st.success(_t("trace.saved"))
            st.rerun()
    errors = trace_gate_errors(candidate, traces)
    if errors:
        st.warning(_t("trace.incomplete", count=len(errors)))
        with st.expander(_t("trace.incomplete_label"), expanded=False):
            for error in errors:
                st.write(f"- {error}")
    else:
        st.success(_t("trace.passed"))
    return errors


def _render_candidate_review(
    repository: ExtractionRepository,
    allowed_candidate_ids: set[str],
) -> None:
    st.divider()
    st.subheader(_t("candidate.title"))
    st.caption(_t("candidate.caption"))

    status_labels: dict[str, CandidateStatus | None] = {
        _t("status.all"): None,
        _t("status.pending"): CandidateStatus.PENDING,
        _t("status.approved"): CandidateStatus.APPROVED,
        _t("status.hold"): CandidateStatus.ON_HOLD,
        _t("status.rejected"): CandidateStatus.REJECTED,
    }
    selected_status_label = st.selectbox(
        _t("candidate.filter"), list(status_labels), key="candidate_status_filter"
    )
    candidates = [
        item
        for item in repository.list_candidates(status=status_labels[selected_status_label])
        if item.id in allowed_candidate_ids
    ]
    if not candidates:
        st.info(_t("candidate.none"))
        return

    status_text = {
        CandidateStatus.PENDING: _t("status.pending"),
        CandidateStatus.APPROVED: _t("status.approved"),
        CandidateStatus.ON_HOLD: _t("status.hold"),
        CandidateStatus.REJECTED: _t("status.rejected"),
    }
    selectable_ids = [item.id for item in candidates]
    if st.session_state.get("review_candidate_id") not in selectable_ids:
        st.session_state.pop("review_candidate_id", None)
    selected_id = st.selectbox(
        _t("candidate.select"),
        selectable_ids,
        format_func=lambda candidate_id: next(
            (
                f"{item.candidate.name} [{status_text[item.status]}]"
                for item in candidates
                if item.id == candidate_id
            ),
            candidate_id,
        ),
        key="review_candidate_id",
    )
    saved = next(item for item in candidates if item.id == selected_id)
    candidate = saved.candidate
    st.write(
        _t(
            "candidate.state",
            status=status_text[saved.status],
            confidence=candidate.confidence,
        )
    )
    st.caption(_t("extract.confidence_reason", reason=candidate.confidence_reason))

    with st.expander(_t("candidate.sources_locked"), expanded=True):
        for reference in candidate.source_references:
            st.caption(_t("candidate.document_id", document_id=reference.document_id))
            st.code(reference.quote, language=None, wrap_lines=True)
            st.write(reference.reason)

    with st.form(f"candidate_edit_{saved.id}"):
        name = st.text_input(_t("candidate.name"), value=candidate.name)
        description = st.text_area(_t("candidate.description"), value=candidate.description)
        category = st.text_input(_t("candidate.category"), value=candidate.category)
        generality = st.text_input(_t("candidate.generality"), value=candidate.generality)
        triggers = st.text_area(_t("candidate.triggers"), value="\n".join(candidate.triggers))
        do_not_use_when = st.text_area(
            _t("candidate.exclusions"), value="\n".join(candidate.do_not_use_when)
        )
        principles = st.text_area(_t("candidate.principles"), value="\n".join(candidate.principles))
        workflow = st.text_area(
            _t("candidate.steps"),
            value="\n".join(step.action for step in candidate.workflow),
        )
        constraints = st.text_area(
            _t("candidate.constraints"), value="\n".join(candidate.constraints)
        )
        warnings = st.text_area(_t("candidate.warnings"), value="\n".join(candidate.warnings))
        save_edit = st.form_submit_button(_t("candidate.save_edit"))

    if save_edit:
        actions = _split_review_lines(workflow)
        edited_data = candidate.model_dump(mode="json")
        edited_data.update(
            {
                "name": name.strip(),
                "description": description.strip(),
                "category": category.strip(),
                "generality": generality.strip(),
                "triggers": _split_review_lines(triggers),
                "do_not_use_when": _split_review_lines(do_not_use_when),
                "principles": _split_review_lines(principles),
                "workflow": [
                    {"order": index, "action": action}
                    for index, action in enumerate(actions, start=1)
                ],
                "constraints": _split_review_lines(constraints),
                "warnings": _split_review_lines(warnings),
            }
        )
        try:
            edited = ExtractedCandidate.model_validate(edited_data)
            repository.update_candidate(saved.id, edited)
        except (ValidationError, ValueError) as exc:
            st.error(_t("candidate.edit_failed", error=exc))
        else:
            _invalidate_current_approval()
            st.success(_t("candidate.edited"))
            st.rerun()

    trace_errors = _render_instruction_trace_review(repository, saved)
    if saved.status is CandidateStatus.APPROVED and trace_errors:
        st.warning(_t("candidate.old_trace"))

    st.caption(_t("candidate.status_only"))
    status_actions = [
        (_t("candidate.reset"), CandidateStatus.PENDING),
        (_t("candidate.approve"), CandidateStatus.APPROVED),
        (_t("candidate.hold"), CandidateStatus.ON_HOLD),
        (_t("candidate.reject"), CandidateStatus.REJECTED),
    ]
    columns = st.columns(len(status_actions))
    for column, (label, status) in zip(columns, status_actions, strict=True):
        if column.button(
            label,
            key=f"candidate_{status.value}_{saved.id}",
            disabled=status is CandidateStatus.APPROVED and bool(trace_errors),
        ):
            repository.set_candidate_status(saved.id, status)
            if status is CandidateStatus.APPROVED:
                st.session_state["current_approved_candidate_id"] = saved.id
            elif st.session_state.get("current_approved_candidate_id") == saved.id:
                _invalidate_current_approval()
            st.rerun()


def _render_duplicate_review(
    repository: ExtractionRepository,
    allowed_candidate_ids: set[str],
) -> None:
    st.divider()
    st.subheader(_t("duplicate.title"))
    st.caption(_t("duplicate.caption"))
    active_candidates = [
        item
        for item in repository.list_candidates()
        if item.id in allowed_candidate_ids
        and item.status in {CandidateStatus.PENDING, CandidateStatus.APPROVED}
    ]
    pairs = find_duplicate_candidates([(item.id, item.candidate) for item in active_candidates])
    if not pairs:
        st.info(_t("duplicate.none"))
        return

    candidates_by_id = {item.id: item for item in active_candidates}
    pair_keys = [f"{pair.left_id}|{pair.right_id}" for pair in pairs]
    pair_by_key = dict(zip(pair_keys, pairs, strict=True))
    selected_pair_key = st.selectbox(
        _t("duplicate.select"),
        pair_keys,
        format_func=lambda key: (
            f"{candidates_by_id[pair_by_key[key].left_id].candidate.name} / "
            f"{candidates_by_id[pair_by_key[key].right_id].candidate.name} "
            f"({pair_by_key[key].score:.0%})"
        ),
        key="duplicate_pair",
    )
    pair = pair_by_key[selected_pair_key]
    pair_ids = [pair.left_id, pair.right_id]
    primary_id = st.radio(
        _t("duplicate.primary_select"),
        pair_ids,
        format_func=lambda candidate_id: candidates_by_id[candidate_id].candidate.name,
        key="merge_primary_candidate",
    )
    secondary_id = next(candidate_id for candidate_id in pair_ids if candidate_id != primary_id)
    primary = candidates_by_id[primary_id]
    secondary = candidates_by_id[secondary_id]
    st.write(_t("duplicate.reasons", reasons=", ".join(pair.reasons)))
    columns = st.columns(2)
    for column, label, saved in (
        (columns[0], _t("duplicate.primary"), primary),
        (columns[1], _t("duplicate.secondary"), secondary),
    ):
        with column:
            st.markdown(f"**{label}: {saved.candidate.name}**")
            st.write(saved.candidate.description)
            st.caption(
                _t(
                    "duplicate.state_sources",
                    status=saved.status.value,
                    sources=len(saved.candidate.source_references),
                )
            )

    merged = merge_candidate_data(primary.candidate, secondary.candidate)
    with st.expander(_t("duplicate.preview"), expanded=True):
        st.write(_t("duplicate.merged_name", name=merged.name))
        st.write(_t("duplicate.merged_description", description=merged.description))
        st.write(_t("duplicate.merged_sources", count=len(merged.source_references)))
        st.write(
            _t(
                "duplicate.merged_steps",
                steps=len(merged.workflow),
                principles=len(merged.principles),
            )
        )
        st.caption(_t("duplicate.after_caption"))

    confirmed = st.checkbox(
        _t("duplicate.confirm"),
        key=f"confirm_merge_{selected_pair_key}",
    )
    if st.button(
        _t("duplicate.merge"),
        disabled=not confirmed,
        key=f"merge_candidates_{selected_pair_key}",
    ):
        try:
            saved_merge = repository.create_merged_candidate(
                primary_id,
                secondary_id,
                merged,
            )
        except ValueError as exc:
            st.error(_t("duplicate.failed", error=exc))
        else:
            current_ids = [
                candidate_id
                for candidate_id in st.session_state.get("current_candidate_ids", [])
                if candidate_id not in {primary_id, secondary_id}
            ]
            current_ids.append(saved_merge.id)
            st.session_state["current_candidate_ids"] = current_ids
            _invalidate_current_approval()
            st.success(_t("duplicate.saved"))
            st.rerun()


def _render_skill_dna(
    candidate_repository: ExtractionRepository,
    skill_repository: SkillDNARepository,
    allowed_candidate_ids: set[str],
) -> None:
    st.divider()
    st.subheader(_t("skill_dna.title"))
    st.caption(_t("skill_dna.caption"))
    approved_candidates = candidate_repository.list_candidates(status=CandidateStatus.APPROVED)
    approved = [
        item
        for item in approved_candidates
        if item.id in allowed_candidate_ids
        and not trace_gate_errors(item.candidate, item.instruction_traces)
    ]
    blocked_count = len(approved_candidates) - len(approved)
    if blocked_count:
        st.warning(_t("skill_dna.blocked", count=blocked_count))
    if not approved:
        st.info(_t("skill_dna.none"))
        return

    selected_id = st.selectbox(
        _t("skill_dna.select"),
        [item.id for item in approved],
        format_func=lambda candidate_id: next(
            item.candidate.name for item in approved if item.id == candidate_id
        ),
        key="skill_dna_candidate_id",
    )
    saved = next(item for item in approved if item.id == selected_id)
    service = SkillDNAService(candidate_repository, skill_repository)
    try:
        preview = service.preview_approved_candidate(selected_id)
    except ValueError as exc:
        st.error(_t("skill_dna.prepare_failed", error=exc))
        return

    columns = st.columns(2)
    with columns[0]:
        st.markdown(_t("skill_dna.before"))
        st.json(saved.candidate.model_dump(mode="json"))
    with columns[1]:
        st.markdown(_t("skill_dna.after", version=preview.version))
        st.json(preview.model_dump(mode="json"))

    existing = skill_repository.get_by_candidate(selected_id)
    action = _t("skill_dna.update" if existing else "skill_dna.save")
    confirmed = st.checkbox(
        _t("skill_dna.confirm"),
        key=f"confirm_skill_dna_{selected_id}",
    )
    if st.button(action, disabled=not confirmed, key=f"save_skill_dna_{selected_id}"):
        try:
            stored = service.convert_approved_candidate(selected_id)
        except ValueError as exc:
            st.error(_t("skill_dna.failed", error=exc))
        else:
            st.session_state["skill_dna_notice_data"] = (
                stored.name,
                stored.version,
            )
            st.rerun()

    if notice_data := st.session_state.pop("skill_dna_notice_data", None):
        st.success(
            _t(
                "skill_dna.saved",
                name=notice_data[0],
                version=notice_data[1],
            )
        )
    current = skill_repository.get_by_candidate(selected_id)
    if current is not None:
        versions = skill_repository.list_versions(current.id)
        st.caption(
            _t(
                "skill_dna.history",
                current=current.version,
                versions=", ".join(item.version for item in versions),
            )
        )


def _render_skill_export(
    skill_repository: SkillDNARepository,
    export_repository: ExportRepository,
    allowed_candidate_id: str,
) -> None:
    st.divider()
    st.subheader(_t("export.title"))
    st.caption(_t("export.caption"))
    stored_skills = [
        skill
        for skill in skill_repository.list_all()
        if skill.candidate_id == allowed_candidate_id
    ]
    skills = []
    blocked_count = 0
    for stored_skill in stored_skills:
        try:
            export_repository.assert_exportable(stored_skill)
        except ValueError:
            blocked_count += 1
        else:
            skills.append(stored_skill)
    if blocked_count:
        st.warning(_t("export.blocked", count=blocked_count))
    if not skills:
        st.info(_t("export.none"))
        return
    selected_id = st.selectbox(
        _t("export.select"),
        [skill.id for skill in skills],
        format_func=lambda skill_id: next(
            f"{skill.name} v{skill.version}" for skill in skills if skill.id == skill_id
        ),
        key="export_skill_dna_id",
    )
    skill = next(item for item in skills if item.id == selected_id)
    destination = st.text_input(
        _t("export.destination"),
        placeholder=_t("export.placeholder"),
        key="skill_export_destination",
    ).strip()
    if not destination:
        st.info(_t("export.destination_info"))
        return

    service = SkillExportService(export_repository)
    try:
        plan = service.prepare(skill, Path(destination))
    except (OSError, ValueError) as exc:
        st.error(_t("export.prepare_failed", error=exc))
        return
    st.write(_t("export.planned", path=plan.skill_file))
    st.code(plan.content, language="markdown", wrap_lines=True)
    if plan.overwrites_existing:
        st.warning(_t("export.overwrite_warning"))
    preview_confirmed = st.checkbox(
        _t("export.confirm"),
        key=f"confirm_export_preview_{selected_id}",
    )
    overwrite_confirmed = not plan.overwrites_existing or st.checkbox(
        _t("export.confirm_overwrite"),
        key=f"confirm_export_overwrite_{selected_id}",
    )
    if st.button(
        _t("export.button"),
        disabled=not (preview_confirmed and overwrite_confirmed),
        key=f"export_skill_{selected_id}",
    ):
        try:
            exported = service.export(plan, overwrite=plan.overwrites_existing)
        except (OSError, ValueError) as exc:
            st.error(_t("export.failed", error=exc))
        else:
            st.success(_t("export.saved", path=exported))

    history = export_repository.list_for_skill(skill.id)
    if history:
        st.caption(
            _t(
                "export.history",
                history=" / ".join(
                    f"v{item.exported_version} → {item.destination_path}" for item in history
                ),
            )
        )


def _render_skill_feedback(
    skill_repository: SkillDNARepository,
    feedback_repository: SkillFeedbackRepository,
) -> None:
    st.divider()
    st.subheader(_t("feedback.title"))
    st.caption(_t("feedback.caption"))
    skills = skill_repository.list_all()
    if not skills:
        st.info(_t("feedback.none"))
        return

    selected_id = st.selectbox(
        _t("feedback.select"),
        [skill.id for skill in skills],
        format_func=lambda skill_id: next(
            f"{skill.name} v{skill.version}" for skill in skills if skill.id == skill_id
        ),
        key="feedback_skill_dna_id",
    )
    skill = next(item for item in skills if item.id == selected_id)
    usage_labels = {
        SkillUsageStatus.NOT_USED: _t("feedback.not_used"),
        SkillUsageStatus.USED_ONCE: _t("feedback.used_once"),
        SkillUsageStatus.REUSED: _t("feedback.reused"),
    }
    usefulness_labels = {
        SkillUsefulness.NOT_EVALUATED: _t("feedback.not_evaluated"),
        SkillUsefulness.HELPFUL: _t("feedback.helpful"),
        SkillUsefulness.PARTLY_HELPFUL: _t("feedback.partly"),
        SkillUsefulness.NOT_HELPFUL: _t("feedback.not_helpful"),
    }
    usage_status = st.selectbox(
        _t("feedback.usage"),
        list(SkillUsageStatus),
        format_func=usage_labels.get,
        key=f"feedback_usage_{selected_id}",
    )
    usefulness = st.selectbox(
        _t("feedback.usefulness"),
        list(SkillUsefulness),
        format_func=usefulness_labels.get,
        key=f"feedback_usefulness_{selected_id}",
    )
    worked_well = st.text_area(
        _t("feedback.worked"),
        max_chars=2_000,
        key=f"feedback_worked_well_{selected_id}",
    )
    needs_improvement = st.text_area(
        _t("feedback.improve"),
        max_chars=2_000,
        key=f"feedback_needs_improvement_{selected_id}",
    )
    st.warning(_t("feedback.safety"))
    if st.button(_t("feedback.save"), key=f"save_feedback_{selected_id}"):
        try:
            feedback_repository.add(
                skill,
                usage_status=usage_status,
                usefulness=usefulness,
                worked_well=worked_well,
                needs_improvement=needs_improvement,
            )
        except ValueError as exc:
            st.error(_t("feedback.failed", error=exc))
        else:
            st.success(
                _t(
                    "feedback.saved",
                    name=skill.name,
                    version=skill.version,
                )
            )

    history = feedback_repository.list_for_skill(skill.id)
    if history:
        st.dataframe(
            [
                {
                    _t("feedback.date"): item.created_at.isoformat(timespec="seconds"),
                    _t("feedback.version"): item.skill_version,
                    _t("feedback.usage"): usage_labels[item.usage_status],
                    _t("feedback.usefulness"): usefulness_labels[item.usefulness],
                    _t("feedback.good"): item.worked_well,
                    _t("feedback.improvement"): item.needs_improvement,
                }
                for item in reversed(history)
            ],
            width="stretch",
            hide_index=True,
        )


def _render_database_controls(database: Database) -> None:
    st.subheader(_t("database.title"))
    st.write(_t("database.schema", version=database.schema_version))
    st.caption(_t("database.directory", path=database.backups.backup_directory))
    if notice := st.session_state.pop("database_notice", None):
        st.success(
            _t(
                "database.restored",
                name=notice,
            )
        )

    if st.button(_t("database.create")):
        try:
            backup = database.create_backup(reason="manual")
        except (OSError, ValueError) as exc:
            st.error(_t("database.create_failed", error=exc))
        else:
            st.success(_t("database.created", name=backup.path.name))

    backups = database.backups.list_backups()
    if inspection_issues := database.backups.list_issues:
        skipped_names = "、".join(issue.path.name for issue in inspection_issues)
        st.warning(_t("database.skipped", names=skipped_names))
    if not backups:
        st.info(_t("database.none"))
        return
    st.dataframe(
        [
            {
                _t("vault.table_file"): item.path.name,
                _t("database.created_at"): item.created_at.isoformat(timespec="seconds"),
                _t("vault.table_size"): item.size_bytes,
                _t("database.schema_column"): item.schema_version,
                _t("database.integrity"): (
                    _t("database.ok") if item.integrity_ok else _t("database.corrupt")
                ),
            }
            for item in backups
        ],
        width="stretch",
        hide_index=True,
    )
    valid_backups = [item for item in backups if database.backup_is_compatible(item)]
    if not valid_backups:
        st.error(_t("database.no_valid"))
        return
    selected_path = st.selectbox(
        _t("database.restore_select"),
        [str(item.path) for item in valid_backups],
        format_func=lambda path: Path(path).name,
        key="restore_backup_path",
    )
    st.warning(_t("database.restore_warning"))
    restore_confirmed = st.checkbox(
        _t("database.restore_confirm"),
        key="restore_database_confirmed",
    )
    if st.button(_t("database.restore"), disabled=not restore_confirmed):
        try:
            safety = database.restore_backup(Path(selected_path))
        except (OSError, RuntimeError, ValueError) as exc:
            st.error(_t("database.restore_failed", error=exc))
        else:
            st.session_state["database_notice"] = safety.path.name
            st.session_state["restore_database_confirmed"] = False
            st.rerun()


def _load_api_key(settings) -> tuple[SecretStr | None, str | None]:
    if settings.environment != "production":
        return settings.openai_api_key, None
    try:
        return KeyringCredentialStore().get_api_key(), None
    except CredentialStoreError as exc:
        return None, str(exc)


def _render_api_key_settings(settings, api_key: SecretStr | None, error: str | None) -> None:
    st.subheader(_t("credentials.title"))
    key_state = _t("sidebar.key_configured" if api_key is not None else "sidebar.key_missing")
    st.write(_t("credentials.status", state=key_state))
    st.write(_t("credentials.model", model=settings.openai_model))
    st.write(_t("credentials.database", path=settings.resolved_database_path))

    if settings.environment != "production":
        st.caption(_t("credentials.dev_caption"))
        if api_key is None:
            st.warning(_t("credentials.dev_missing"))
        return

    st.caption(_t("credentials.production_caption"))
    if error is not None:
        st.error(error)
        st.warning(_t("credentials.no_plaintext"))
        return

    input_generation = st.session_state.get("credential_input_generation", 0)
    with st.form(f"credential_api_key_form_{input_generation}", clear_on_submit=True):
        entered_key = st.text_input(
            _t("credentials.input"),
            type="password",
            value="",
            placeholder=_t("credentials.placeholder"),
            key=f"credential_api_key_input_{input_generation}",
        )
        save_key = st.form_submit_button(
            _t("credentials.save"),
        )
    if save_key:
        try:
            KeyringCredentialStore().set_api_key(SecretStr(entered_key))
        except (CredentialStoreError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.session_state["credential_input_generation"] = input_generation + 1
            st.session_state["credential_notice_key"] = "credentials.saved"
            st.rerun()

    delete_confirmed = st.checkbox(
        _t("credentials.confirm_delete"),
        key="credential_delete_confirmed",
        disabled=api_key is None,
    )
    if st.button(
        _t("credentials.delete"),
        disabled=api_key is None or not delete_confirmed,
    ):
        try:
            deleted = KeyringCredentialStore().delete_api_key()
        except CredentialStoreError as exc:
            st.error(str(exc))
        else:
            st.session_state["credential_notice_key"] = (
                "credentials.deleted" if deleted else "credentials.none_saved"
            )
            st.rerun()

    if notice_key := st.session_state.pop("credential_notice_key", None):
        st.success(_t(notice_key))


def _set_guided_view(view: GuidedView) -> None:
    st.session_state["guided_view"] = view.value


def _set_ui_language(language: Language) -> None:
    st.session_state["ui_language"] = language


def _guided_eligibility(
    candidate_repository: ExtractionRepository,
) -> GuidedEligibility:
    files: list[VaultFile] = st.session_state.get("vault_files", [])
    durable_selected_paths: list[str] = st.session_state.get("selected_note_paths", [])
    selected_paths: list[str] = st.session_state.get(
        "selected_note_paths_widget",
        durable_selected_paths,
    )
    if selected_paths != durable_selected_paths:
        _invalidate_current_journey(clear_prepared=True)
    notes_selected = note_selection_is_current(
        files,
        selected_paths,
        st.session_state.get("vault_id"),
    )
    had_current_marker = bool(st.session_state.get("current_candidate_ids"))
    candidates = _current_journey_candidates(candidate_repository)
    if had_current_marker and not candidates:
        _invalidate_current_journey(clear_prepared=False)
        st.session_state.pop("payload_confirmed", None)
        st.session_state.pop("cost_confirmed", None)
    approved_id = st.session_state.get("current_approved_candidate_id")
    approved = any(
        item.id == approved_id
        and item.status is CandidateStatus.APPROVED
        and not trace_gate_errors(item.candidate, item.instruction_traces)
        for item in candidates
    )
    return GuidedEligibility(
        notes_selected=notes_selected,
        draft_available=bool(candidates),
        approved_candidate=approved,
    )


def _render_guided_navigation(
    current: GuidedView,
    eligibility: GuidedEligibility,
) -> None:
    views = (
        GuidedView.HOME,
        GuidedView.NOTES,
        GuidedView.DATA,
        GuidedView.REVIEW,
        GuidedView.SAVE,
        GuidedView.SETTINGS,
    )
    labels = {
        GuidedView.HOME: _t("guided.nav.home"),
        GuidedView.NOTES: _t("guided.nav.notes"),
        GuidedView.DATA: _t("guided.nav.data"),
        GuidedView.REVIEW: _t("guided.nav.review"),
        GuidedView.SAVE: _t("guided.nav.save"),
        GuidedView.SETTINGS: _t("guided.nav.settings"),
    }
    for column, view in zip(st.columns(len(views)), views, strict=True):
        column.button(
            labels[view],
            key=f"guided_nav_{view.value}",
            type="primary" if view is current else "secondary",
            disabled=not guided_view_is_eligible(view, eligibility),
            width="stretch",
            on_click=_set_guided_view,
            args=(view,),
        )


def _start_guided_flow(kind: str, sample_vault: Path | None) -> None:
    st.session_state["guided_start_kind"] = kind
    if kind == "sample" and sample_vault is not None:
        st.session_state["vault_path_input"] = str(sample_vault)
        st.session_state["sample_vault_notice"] = True
    _set_guided_view(GuidedView.NOTES)


def _render_guided_home() -> None:
    st.caption(_t("guided.home.eyebrow"))
    st.title(_t("guided.home.title"))
    st.markdown(_t("guided.home.body"))
    sample_vault = _bundled_sample_vault()
    selected = st.session_state.get("guided_start_kind")
    columns = st.columns(2)
    columns[0].button(
        _t("guided.home.sample"),
        key="guided_start_sample",
        type="primary" if selected == "sample" else "secondary",
        disabled=sample_vault is None,
        width="stretch",
        on_click=_start_guided_flow,
        args=("sample", sample_vault),
    )
    columns[1].button(
        _t("guided.home.own"),
        key="guided_start_own",
        type="primary" if selected == "own" else "secondary",
        width="stretch",
        on_click=_start_guided_flow,
        args=("own", sample_vault),
    )
    example_columns = st.columns(2)
    with example_columns[0]:
        with st.container(border=True):
            st.markdown(f"### {_t('guided.home.input')}")
            st.write(_t("guided.home.input_example"))
    with example_columns[1]:
        with st.container(border=True):
            st.markdown(f"### {_t('guided.home.output')}")
            st.write(_t("guided.home.output_example"))
    with st.container(border=True):
        st.markdown(f"### {_t('guided.home.benefit')}")
        st.write(_t("guided.home.benefit_text"))
    with st.expander(_t("guided.home.example_title"), expanded=False):
        st.markdown(_t("guided.home.example_body"))
    st.iframe(
        build_guided_walkthrough_data_uri(_language()),
        height=720,
    )


def _render_step_intro(title_key: str, body_key: str) -> None:
    st.title(_t(title_key))
    st.markdown(_t(body_key))


def _render_step_continue(
    next_view: GuidedView,
    eligibility: GuidedEligibility,
    *,
    label_key: str,
    blocker_key: str,
) -> None:
    if not guided_view_is_eligible(next_view, eligibility):
        st.warning(_t(blocker_key))
    st.button(
        _t(label_key),
        key=f"guided_continue_{next_view.value}",
        type="primary",
        disabled=not guided_view_is_eligible(next_view, eligibility),
        on_click=_set_guided_view,
        args=(next_view,),
    )


def _render_history_resume(
    candidate_repository: ExtractionRepository,
    skill_repository: SkillDNARepository,
) -> None:
    st.subheader(_t("guided.history.title"))
    st.caption(_t("guided.history.body"))
    candidates = candidate_repository.list_candidates()
    if candidates:
        candidates_by_id = {item.id: item for item in candidates}
        selected_candidate_id = st.selectbox(
            _t("guided.history.candidate"),
            [None, *candidates_by_id],
            format_func=lambda candidate_id: (
                _t("guided.history.choose_candidate")
                if candidate_id is None
                else (
                    f"{candidates_by_id[candidate_id].candidate.name} "
                    f"[{candidates_by_id[candidate_id].status.value}]"
                )
            ),
            key="history_candidate_id",
        )
        if selected_candidate_id is not None:
            selected_candidate = candidates_by_id[selected_candidate_id]
            st.json(selected_candidate.candidate.model_dump(mode="json"))
            if st.button(
                _t("guided.history.resume_candidate"),
                key=f"resume_candidate_{selected_candidate_id}",
            ):
                _record_history_resume(
                    selected_candidate.id,
                    selected_candidate.extraction_run_id,
                )
                if (
                    selected_candidate.status is CandidateStatus.APPROVED
                    and not trace_gate_errors(
                        selected_candidate.candidate,
                        selected_candidate.instruction_traces,
                    )
                ):
                    st.session_state["current_approved_candidate_id"] = (
                        selected_candidate.id
                    )
                st.rerun()
    else:
        st.info(_t("guided.history.none_candidates"))

    skills = skill_repository.list_all()
    if skills:
        skills_by_id = {item.id: item for item in skills}
        selected_skill_id = st.selectbox(
            _t("guided.history.skill"),
            [None, *skills_by_id],
            format_func=lambda skill_id: (
                _t("guided.history.choose_skill")
                if skill_id is None
                else f"{skills_by_id[skill_id].name} v{skills_by_id[skill_id].version}"
            ),
            key="history_skill_id",
        )
        if selected_skill_id is not None:
            selected_skill = skills_by_id[selected_skill_id]
            st.json(selected_skill.model_dump(mode="json"))
            try:
                source_candidate = candidate_repository.get_candidate(
                    selected_skill.candidate_id
                )
            except ValueError:
                source_candidate = None
            can_resume_save = bool(
                source_candidate is not None
                and source_candidate.status is CandidateStatus.APPROVED
                and not trace_gate_errors(
                    source_candidate.candidate,
                    source_candidate.instruction_traces,
                )
            )
            if not can_resume_save:
                st.warning(_t("guided.history.not_approved"))
            if st.button(
                _t("guided.history.resume_skill"),
                key=f"resume_skill_{selected_skill_id}",
                disabled=not can_resume_save,
            ):
                assert source_candidate is not None
                _record_history_resume(
                    source_candidate.id,
                    source_candidate.extraction_run_id,
                )
                st.session_state["current_approved_candidate_id"] = source_candidate.id
                _set_guided_view(GuidedView.SAVE)
                st.rerun()
    else:
        st.info(_t("guided.history.none_skills"))


def _render_guided_settings(
    settings,
    api_key: SecretStr | None,
    credential_error: str | None,
    database: Database,
    candidate_repository: ExtractionRepository,
    skill_repository: SkillDNARepository,
    feedback_repository: SkillFeedbackRepository,
) -> None:
    st.title(_t("guided.settings.title"))
    language_tab, api_tab, data_tab, safety_tab, feedback_tab = st.tabs(
        [
            _t("guided.settings.language"),
            _t("guided.settings.api"),
            _t("guided.settings.data"),
            _t("guided.settings.safety"),
            _t("guided.settings.feedback"),
        ]
    )
    with language_tab:
        st.markdown(_t("guided.settings.language_help"))
        language_columns = st.columns(2)
        language_columns[0].button(
            LANGUAGE_LABELS["en"],
            key="guided_settings_language_en",
            type="primary" if _language() == "en" else "secondary",
            on_click=_set_ui_language,
            args=("en",),
            width="stretch",
        )
        language_columns[1].button(
            LANGUAGE_LABELS["ja"],
            key="guided_settings_language_ja",
            type="primary" if _language() == "ja" else "secondary",
            on_click=_set_ui_language,
            args=("ja",),
            width="stretch",
        )
    with api_tab:
        _render_api_key_settings(settings, api_key, credential_error)
    with data_tab:
        _render_database_controls(database)
    with safety_tab:
        st.info(_t("guided.settings.safety_body"))
        st.markdown(_t("local_first.body"))
    with feedback_tab:
        _render_history_resume(candidate_repository, skill_repository)
        st.divider()
        _render_first_use_feedback()
        _render_skill_feedback(skill_repository, feedback_repository)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    openai_api_key, credential_error = _load_api_key(settings)

    database = Database(settings.resolved_database_path)
    database.initialize()

    st.set_page_config(
        page_title=settings.app_name,
        page_icon="🧬",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _sync_runtime_extraction_config(
        settings.openai_model,
        settings.openai_reasoning_effort,
        settings.openai_max_output_tokens,
    )
    inject_theme()
    supported_languages: list[Language] = ["en", "ja"]
    if st.session_state.get("ui_language") not in supported_languages:
        st.session_state["ui_language"] = DEFAULT_LANGUAGE
    with st.sidebar:
        st.selectbox(
            text(DEFAULT_LANGUAGE, "language.label"),
            options=supported_languages,
            index=supported_languages.index(DEFAULT_LANGUAGE),
            format_func=LANGUAGE_LABELS.get,
            key="ui_language",
        )
    language = _language()
    render_local_safety_sidebar(
        __release_label__,
        api_key_configured=openai_api_key is not None,
        language=language,
    )
    assert database.session_factory is not None
    extraction_repository = ExtractionRepository(database.session_factory)
    skill_repository = SkillDNARepository(database.session_factory)
    export_repository = ExportRepository(database.session_factory)
    feedback_repository = SkillFeedbackRepository(database.session_factory)
    vault_repository = VaultRepository(database.session_factory)
    extraction_service = ExtractionService(extraction_repository)

    eligibility = _guided_eligibility(extraction_repository)
    requested = st.session_state.get("guided_view", GuidedView.HOME.value)
    current = resolve_guided_view(requested, eligibility)
    if requested != current.value:
        st.session_state["guided_view"] = current.value
    _render_guided_navigation(current, eligibility)
    st.divider()

    if current is GuidedView.HOME:
        _render_guided_home()
    elif current is GuidedView.NOTES:
        _render_step_intro("guided.step.notes.title", "guided.step.notes.body")
        _render_vault_browser(
            vault_repository,
            extraction_service,
            extraction_repository,
            settings.max_input_chars,
            openai_api_key,
            settings.openai_model,
            settings.openai_reasoning_effort,
            settings.openai_max_output_tokens,
            show_payload=False,
        )
        _render_step_continue(
            GuidedView.DATA,
            _guided_eligibility(extraction_repository),
            label_key="guided.continue.data",
            blocker_key="guided.block.notes",
        )
    elif current is GuidedView.DATA:
        _render_step_intro("guided.step.data.title", "guided.step.data.body")
        _render_current_payload(
            vault_repository,
            extraction_service,
            extraction_repository,
            settings.max_input_chars,
            openai_api_key,
            settings.openai_model,
            settings.openai_reasoning_effort,
            settings.openai_max_output_tokens,
        )
        _render_step_continue(
            GuidedView.REVIEW,
            _guided_eligibility(extraction_repository),
            label_key="guided.continue.review",
            blocker_key="guided.block.draft",
        )
    elif current is GuidedView.REVIEW:
        _render_step_intro("guided.step.review.title", "guided.step.review.body")
        current_candidate_ids = {
            item.id for item in _current_journey_candidates(extraction_repository)
        }
        _render_candidate_review(extraction_repository, current_candidate_ids)
        with st.expander(_t("duplicate.title"), expanded=False):
            _render_duplicate_review(extraction_repository, current_candidate_ids)
        _render_step_continue(
            GuidedView.SAVE,
            _guided_eligibility(extraction_repository),
            label_key="guided.continue.save",
            blocker_key="guided.block.approved",
        )
    elif current is GuidedView.SAVE:
        _render_step_intro("guided.step.save.title", "guided.step.save.body")
        approved_candidate_id = st.session_state["current_approved_candidate_id"]
        _render_skill_dna(
            extraction_repository,
            skill_repository,
            {approved_candidate_id},
        )
        _render_skill_export(
            skill_repository,
            export_repository,
            approved_candidate_id,
        )
    else:
        _render_guided_settings(
            settings,
            openai_api_key,
            credential_error,
            database,
            extraction_repository,
            skill_repository,
            feedback_repository,
        )


if __name__ == "__main__":
    main()
