from __future__ import annotations

from datetime import UTC, datetime
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
    SkillDNARepository,
    SkillFeedbackRepository,
    VaultRepository,
)
from skill_dna_compiler.ui import (
    inject_theme,
    render_hero,
    render_local_safety_sidebar,
    render_workflow,
)
from skill_dna_compiler.vault import (
    MarkdownParseError,
    VaultFile,
    VaultScanError,
    parse_markdown_file,
    scan_vault,
)


def _render_extraction_result(
    result: ExtractionResult,
    prepared: PreparedPayload,
    *,
    provider_label: str,
) -> None:
    st.success(f"{provider_label}が完了しました。候補数: {len(result.candidates)}")
    if not result.candidates:
        st.info("再利用可能なSkill候補は見つかりませんでした。これは正常な結果です。")
        return

    documents = {item.document_id: item for item in prepared.payload.documents}
    st.markdown("### 検証済みSkill候補")
    st.caption("まだ承認・Skill化されていません。次のPhaseで編集と承認を追加します。")
    for index, candidate in enumerate(result.candidates, start=1):
        with st.expander(f"{index}. {candidate.name}（信頼度 {candidate.confidence:.0%}）"):
            st.write(candidate.description)
            st.write(f"カテゴリ: `{candidate.category}` / 一般性: `{candidate.generality}`")
            st.write(f"信頼度の理由: {candidate.confidence_reason}")
            if candidate.triggers:
                st.markdown("**利用場面**")
                for trigger in candidate.triggers:
                    st.markdown(f"- {trigger}")
            if candidate.workflow:
                st.markdown("**手順**")
                for step in candidate.workflow:
                    st.markdown(f"{step.order}. {step.action}")
            st.markdown("**検証済み引用**")
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
    openai_api_key: SecretStr | None,
    openai_model: str,
    reasoning_effort: str,
    max_output_tokens: int,
    document_ids_by_path: dict[str, str],
) -> None:
    st.subheader("2. AI送信内容の安全確認と抽出")
    st.caption(
        "準備しただけでは送信しません。伏字後のJSONと料金目安を確認し、"
        "実抽出を二重確認した場合だけOpenAIへ送信します。"
    )

    selection_signature = tuple(selected_paths)
    if st.session_state.get("prepared_selection") != selection_signature:
        st.session_state.pop("prepared_payload", None)
        st.session_state.pop("extraction_result", None)
        st.session_state.pop("extraction_provider_label", None)
        st.session_state.pop("payload_confirmed", None)
        st.session_state.pop("cost_confirmed", None)
        st.session_state.pop("actual_api_usage", None)

    if not selected_paths:
        st.info("AI分析対象候補から1件以上のメモを選択してください。")
        return

    if st.button("送信内容を準備する"):
        selected_files = [item for item in files if item.relative_path in selected_paths]
        try:
            notes = [parse_markdown_file(item) for item in selected_files]
            prepared = prepare_extraction_payload(
                notes,
                max_characters=max_input_chars,
                document_ids_by_path=document_ids_by_path,
            )
        except (MarkdownParseError, PayloadLimitError, ValueError) as exc:
            st.session_state.pop("prepared_payload", None)
            st.error(str(exc))
        else:
            st.session_state["prepared_payload"] = prepared
            st.session_state["prepared_selection"] = selection_signature
            st.session_state.pop("extraction_result", None)
            st.session_state.pop("extraction_provider_label", None)
            st.session_state.pop("payload_confirmed", None)
            st.session_state.pop("cost_confirmed", None)
            st.session_state.pop("actual_api_usage", None)

    prepared: PreparedPayload | None = st.session_state.get("prepared_payload")
    if prepared is None:
        return

    st.write(
        f"送信予定: **{len(prepared.payload.documents)}件** / "
        f"**{prepared.character_count:,}文字** / "
        f"伏字 **{prepared.payload.redaction_count}件**"
    )
    if prepared.findings:
        st.warning("秘密情報または個人情報の可能性がある箇所を自動で伏字にしました。")
        st.dataframe(
            [
                {
                    "ファイル": item.document_path,
                    "場所": item.location,
                    "行": item.finding.line,
                    "種類": item.finding.kind,
                    "重要度": item.finding.severity.value,
                    "置換": item.finding.replacement,
                }
                for item in prepared.findings
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.success("既知の秘密情報・連絡先パターンは検出されませんでした。")

    st.markdown("#### 実際に送信されるJSON")
    st.code(prepared.serialized_json, language="json", wrap_lines=True)

    estimate = None
    try:
        estimate = estimate_extraction_cost(
            prepared.payload,
            model=openai_model,
            max_output_tokens=max_output_tokens,
        )
    except PricingUnavailableError:
        st.error(
            "設定中のモデルは料金情報を確認できていないため、実API抽出を無効にしました。"
        )
    else:
        st.markdown("#### 実APIの入力規模・料金目安")
        st.write(f"モデル: `{estimate.model}` / reasoning effort: `{reasoning_effort}`")
        st.write(
            f"入力推定: **{estimate.input_tokens_low:,}～"
            f"{estimate.input_tokens_high:,} tokens** / "
            f"最大出力: **{estimate.max_output_tokens:,} tokens**"
        )
        st.write(
            f"入力料金目安: **${estimate.input_cost_low_usd:.4f}～"
            f"${estimate.input_cost_high_usd:.4f}** / "
            f"最大出力まで使った場合の上限目安: **${estimate.maximum_total_usd:.4f}**"
        )
        st.caption(
            f"料金確認日: {PRICING_REVIEWED_ON}。"
            "ローカル推定のため実請求額とは異なる場合があります。"
        )
        st.link_button(
            "OpenAI公式料金を確認する",
            "https://developers.openai.com/api/docs/pricing",
        )
        if estimate.long_context_pricing_possible:
            st.warning(
                "長い入力向けの割増料金に入る可能性があるため、上限目安へ割増を反映しました。"
            )

    confirmed = st.checkbox(
        "伏字済みの送信内容を確認しました",
        key="payload_confirmed",
    )
    if st.button("モック抽出を実行する", disabled=not confirmed):
        st.session_state.pop("actual_api_usage", None)
        try:
            result = extraction_service.run(
                payload=prepared.payload,
                provider=StaticMockExtractionProvider(
                    build_demo_extraction_result(prepared.payload)
                ),
                model="mock-local",
                prompt_version="static-mock-v1",
            )
        except ExtractionProviderError as exc:
            st.session_state.pop("extraction_result", None)
            st.session_state.pop("extraction_provider_label", None)
            st.error(exc.user_message)
            if exc.retryable:
                st.caption("内容を変更せず、同じボタンから再試行できます。")
        else:
            st.session_state["extraction_result"] = result
            st.session_state["extraction_provider_label"] = "モック抽出"

    if openai_api_key is None:
        st.warning("OpenAI APIキーが未設定のため、実API抽出は利用できません。")
    if st.session_state.pop("reset_live_confirmation", False):
        st.session_state["cost_confirmed"] = False
    cost_confirmed = st.checkbox(
        "表示された料金目安を確認し、API料金の発生に同意します",
        key="cost_confirmed",
    )
    live_disabled = (
        not confirmed
        or not cost_confirmed
        or openai_api_key is None
        or estimate is None
    )
    if st.button(
        "OpenAIで実抽出する（API料金が発生します）",
        type="primary",
        disabled=live_disabled,
    ):
        assert openai_api_key is not None
        st.session_state["reset_live_confirmation"] = True
        provider = OpenAIExtractionProvider.from_api_key(
            api_key=openai_api_key,
            model=openai_model,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
        )
        try:
            with st.spinner("OpenAIでSkill候補を抽出しています…"):
                result = extraction_service.run(
                    payload=prepared.payload,
                    provider=provider,
                    model=openai_model,
                    prompt_version=PROMPT_VERSION,
                )
        except ExtractionProviderError as exc:
            st.session_state.pop("extraction_result", None)
            st.session_state.pop("extraction_provider_label", None)
            st.error(exc.user_message)
            if exc.retryable:
                st.caption("送信内容と料金目安を再確認してから再試行できます。")
        else:
            st.session_state["extraction_result"] = result
            st.session_state["extraction_provider_label"] = "OpenAI実抽出"
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
        provider_label = st.session_state.get("extraction_provider_label", "抽出")
        _render_extraction_result(result, prepared, provider_label=provider_label)
        actual_usage = st.session_state.get("actual_api_usage")
        if provider_label == "OpenAI実抽出" and actual_usage is not None:
            st.info(
                "実API使用量: "
                f"入力 {actual_usage['input_tokens']:,} / "
                f"出力 {actual_usage['output_tokens']:,} / "
                f"合計 {actual_usage['total_tokens']:,} tokens / "
                f"料金推定 ${actual_usage['cost_usd']}"
            )
        if provider_label == "モック抽出":
            st.caption("ネットワーク通信とAPI料金は発生していません。")


def _render_vault_browser(
    repository: VaultRepository,
    extraction_service: ExtractionService,
    max_input_chars: int,
    openai_api_key: SecretStr | None,
    openai_model: str,
    reasoning_effort: str,
    max_output_tokens: int,
) -> None:
    st.subheader("1. Obsidianメモを選ぶ")
    st.caption("現在は開発版のため、Vaultフォルダの絶対パスを貼り付けてください。")
    saved_vault = repository.latest()
    vault_path = st.text_input(
        "Vaultフォルダ",
        value=saved_vault.root_path if saved_vault else "",
        placeholder=r"C:\Users\name\Documents\My Vault",
    )
    exclusions = st.text_input(
        "除外フォルダ（カンマ区切り）",
        value=(
            ",".join(saved_vault.exclude_paths)
            if saved_vault
            else ".obsidian,.git,.trash,node_modules"
        ),
    )

    if st.button("Vaultを読み込む", type="primary"):
        if not vault_path.strip():
            st.warning("Vaultフォルダの絶対パスを入力してください。")
            return
        excluded_paths = tuple(item.strip() for item in exclusions.split(",") if item.strip())
        try:
            files = scan_vault(
                Path(vault_path.strip()), exclude_paths=excluded_paths
            )
            vault_id = repository.save_scan(
                Path(vault_path.strip()), excluded_paths, files
            )
            st.session_state["vault_id"] = vault_id
            st.session_state["vault_files"] = files
            st.session_state.pop("vault_error", None)
            for key in (
                "selected_note_paths",
                "prepared_payload",
                "prepared_selection",
                "extraction_result",
                "extraction_provider_label",
                "payload_confirmed",
                "cost_confirmed",
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

    st.success(f"Markdownメモを{len(files)}件読み込みました。元ファイルは変更していません。")
    folders = sorted({str(Path(item.relative_path).parent).replace("\\", "/") for item in files})
    selected_folder = st.selectbox("フォルダで絞り込み", options=["すべて", *folders])
    search_text = st.text_input("ファイル名・パスで検索").strip().casefold()
    filtered = [
        item
        for item in files
        if not search_text
        or search_text in item.title.casefold()
        or search_text in item.relative_path.casefold()
        if selected_folder == "すべて"
        or str(Path(item.relative_path).parent).replace("\\", "/") == selected_folder
    ]

    st.dataframe(
        [
            {
                "ファイル": item.title,
                "パス": item.relative_path,
                "サイズ": item.size_bytes,
                "更新日時": item.modified_at.isoformat(timespec="seconds"),
            }
            for item in filtered
        ],
        width="stretch",
        hide_index=True,
    )
    if not filtered:
        st.warning("検索条件に一致するメモはありません。")
        return

    selected_paths = st.multiselect(
        "AI分析対象候補（まだ送信されません）",
        options=[item.relative_path for item in filtered],
        key="selected_note_paths",
    )
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
        "プレビューするメモ",
        options=[item.relative_path for item in filtered],
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
    st.divider()
    _render_extraction_preview(
        files,
        selected_paths,
        max_input_chars,
        extraction_service,
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
    approved_count = sum(
        trace.review_status is TraceReviewStatus.APPROVED for trace in traces
    )
    st.markdown("#### 根拠の確認（DNA Trace）")
    st.caption(
        f"根拠確認を通過 {approved_count}/{len(traces)}。"
        "Skillへ入れる各ルールを、元メモと照合します。"
    )
    st.progress(
        approved_count / len(traces),
        text=f"Skillへ入れられるルール: {approved_count}/{len(traces)}",
    )
    with st.expander("この画面でやること", expanded=approved_count == 0):
        st.markdown(
            """
            1. このルールを直接支える引用を選びます。
            2. 引用とルールの意味が同じか、危険な操作を含むか確認します。
            3. 承認・保留・却下を選び、確認結果を保存します。

            分からない場合は**保留**のままで大丈夫です。未確認のルールはSkillへ出力されません。
            """
        )

    def instruction_label(key: str) -> str:
        trace = traces_by_key[key]
        status = {
            TraceReviewStatus.PENDING: "未確認",
            TraceReviewStatus.APPROVED: "承認済み",
            TraceReviewStatus.REJECTED: "却下",
        }[trace.review_status]
        return f"[{status}] {key} — {instruction_by_key[key].text}"

    selected_key = st.selectbox(
        "確認する指示",
        [item.key for item in instructions],
        format_func=instruction_label,
        key=f"trace_instruction_{saved.id}",
    )
    selected = traces_by_key[selected_key]
    source_options = {
        source_reference_fingerprint(source): source
        for source in candidate.source_references
    }
    with st.form(f"trace_review_{saved.id}_{selected_key}"):
        st.code(instruction_by_key[selected_key].text, language=None, wrap_lines=True)
        selected_sources = st.multiselect(
            "この指示を直接支える引用",
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
            "元メモに、このルールを直接支える内容がありますか？",
            [0, 1, 2],
            index=selected.traceability,
            format_func=lambda value: {
                0: "いいえ（根拠がない）",
                1: "関連する内容はある",
                2: "はい（直接書かれている）",
            }[value],
            help="DNA Traceの詳細評価名では「追跡可能性」です。承認には直接根拠が必要です。",
        )
        fidelity = st.selectbox(
            "引用とルールの意味・条件は一致していますか？",
            [0, 1, 2],
            index=selected.fidelity,
            format_func=lambda value: {
                0: "一致しない、または書かれていない意味が増えている",
                1: "一部一致するが、条件が足りない",
                2: "意味と条件が一致している",
            }[value],
            help="DNA Traceの詳細評価名では「意味の一致」です。承認には完全な一致が必要です。",
        )
        impact_options: list[bool | None] = [None, False, True]
        high_impact = st.selectbox(
            "お金・削除・公開などに大きく影響するルールですか？",
            impact_options,
            index=impact_options.index(selected.high_impact),
            format_func=lambda value: {
                None: "まだ判断していない（承認不可）",
                False: "いいえ、通常のルール",
                True: "はい、影響が大きい",
            }[value],
            help="削除、支払い、公開、外部送信など、失敗時の影響が大きい指示かを確認します。",
        )
        boundary_options: list[int | None] = [None, 0, 1, 2]
        boundary = st.selectbox(
            "重要な使用条件や、してはいけないことは十分ですか？",
            boundary_options,
            index=boundary_options.index(selected.boundary),
            format_func=lambda value: {
                None: "まだ確認していない／高影響でなければ対象外",
                0: "不足している",
                1: "一部あるが不十分",
                2: "十分に書かれている",
            }[value],
            help="影響が大きいルールを承認する場合だけ、十分な条件と禁止事項が必要です。",
        )
        decision = st.selectbox(
            "このルールをどうしますか？",
            list(TraceReviewStatus),
            index=list(TraceReviewStatus).index(selected.review_status),
            format_func=lambda value: {
                TraceReviewStatus.PENDING: "保留",
                TraceReviewStatus.APPROVED: "承認",
                TraceReviewStatus.REJECTED: "却下",
            }[value],
        )
        reviewer_note = st.text_input(
            "確認メモ（任意・秘密やメモ本文は記録しない）",
            value=selected.reviewer_note,
        )
        save_trace = st.form_submit_button("このルールの確認結果を保存")
    with st.expander("DNA Traceの評価用語を見る", expanded=False):
        st.markdown(
            """
            - **追跡可能性**: 元メモがルールを直接支えているか
            - **意味の一致**: 引用にない条件や命令が増えていないか
            - **影響度**: お金・削除・公開・外部送信などへの影響が大きいか
            - **使用条件・禁則**: 高影響なルールを安全に使う境界が十分か
            """
        )
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
                    datetime.now(UTC)
                    if decision is not TraceReviewStatus.PENDING
                    else None
                ),
            )
            repository.save_instruction_trace(saved.id, trace)
        except (ValidationError, ValueError) as exc:
            st.error(f"DNA Traceを保存できません: {exc}")
        else:
            st.success("DNA Traceを保存しました。候補全体は未確認へ戻ります。")
            st.rerun()
    errors = trace_gate_errors(candidate, traces)
    if errors:
        st.warning(f"未完了のため承認できません（{len(errors)}件）。")
        with st.expander("未完了項目を確認", expanded=False):
            for error in errors:
                st.write(f"- {error}")
    else:
        st.success("すべての指示がDNA Trace gateを満たしています。")
    return errors


def _render_candidate_review(repository: ExtractionRepository) -> None:
    st.divider()
    st.subheader("3. Skill候補をレビューする")
    st.caption(
        "候補はローカルDBに保存されています。承認しても、この段階ではSkillの生成や出力は行いません。"
    )

    status_labels: dict[str, CandidateStatus | None] = {
        "すべて": None,
        "未確認": CandidateStatus.PENDING,
        "承認済み": CandidateStatus.APPROVED,
        "保留": CandidateStatus.ON_HOLD,
        "却下": CandidateStatus.REJECTED,
    }
    selected_status_label = st.selectbox(
        "表示する状態", list(status_labels), key="candidate_status_filter"
    )
    candidates = repository.list_candidates(
        status=status_labels[selected_status_label]
    )
    if not candidates:
        st.info("表示できるSkill候補はまだありません。")
        return

    selected_id = st.selectbox(
        "レビューする候補",
        [item.id for item in candidates],
        format_func=lambda candidate_id: next(
            (
                f"{item.candidate.name} [{item.status.value}]"
                for item in candidates
                if item.id == candidate_id
            ),
            candidate_id,
        ),
        key="review_candidate_id",
    )
    saved = next(item for item in candidates if item.id == selected_id)
    candidate = saved.candidate
    st.write(f"現在の状態: `{saved.status.value}` / 信頼度: `{candidate.confidence:.0%}`")
    st.caption(f"信頼度の理由: {candidate.confidence_reason}")

    with st.expander("変更できない引用元", expanded=True):
        for reference in candidate.source_references:
            st.caption(f"文書ID: {reference.document_id}")
            st.code(reference.quote, language=None, wrap_lines=True)
            st.write(reference.reason)

    with st.form(f"candidate_edit_{saved.id}"):
        name = st.text_input("候補名", value=candidate.name)
        description = st.text_area("説明", value=candidate.description)
        category = st.text_input("カテゴリ", value=candidate.category)
        generality = st.text_input("汎用性", value=candidate.generality)
        triggers = st.text_area("利用場面（1行に1件）", value="\n".join(candidate.triggers))
        do_not_use_when = st.text_area(
            "利用しない場面（1行に1件）", value="\n".join(candidate.do_not_use_when)
        )
        principles = st.text_area("原則（1行に1件）", value="\n".join(candidate.principles))
        workflow = st.text_area(
            "手順（1行に1件）",
            value="\n".join(step.action for step in candidate.workflow),
        )
        constraints = st.text_area("制約（1行に1件）", value="\n".join(candidate.constraints))
        warnings = st.text_area("注意事項（1行に1件）", value="\n".join(candidate.warnings))
        save_edit = st.form_submit_button("編集内容を保存")

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
            st.error(f"編集内容を保存できません: {exc}")
        else:
            st.success("編集内容を保存し、状態を未確認へ戻しました。")
            st.rerun()

    trace_errors = _render_instruction_trace_review(repository, saved)
    if saved.status is CandidateStatus.APPROVED and trace_errors:
        st.warning(
            "この候補は以前の版で承認済みですが、現行のDNA Trace確認は未完了です。"
            "再確認が終わるまでSkill DNA化と出力はできません。"
        )

    st.caption("状態の変更は候補データだけに保存され、Skillファイルは作成されません。")
    status_actions = [
        ("未確認に戻す", CandidateStatus.PENDING),
        ("承認する", CandidateStatus.APPROVED),
        ("保留にする", CandidateStatus.ON_HOLD),
        ("却下する", CandidateStatus.REJECTED),
    ]
    columns = st.columns(len(status_actions))
    for column, (label, status) in zip(columns, status_actions, strict=True):
        if column.button(
            label,
            key=f"candidate_{status.value}_{saved.id}",
            disabled=status is CandidateStatus.APPROVED and bool(trace_errors),
        ):
            repository.set_candidate_status(saved.id, status)
            st.rerun()


def _render_duplicate_review(repository: ExtractionRepository) -> None:
    st.divider()
    st.subheader("任意: 重複候補を確認する")
    st.caption(
        "類似度はローカルで計算する参考情報です。自動統合はせず、選択と確認後だけ新しい未確認候補を作ります。"
    )
    active_candidates = [
        item
        for item in repository.list_candidates()
        if item.status in {CandidateStatus.PENDING, CandidateStatus.APPROVED}
    ]
    pairs = find_duplicate_candidates(
        [(item.id, item.candidate) for item in active_candidates]
    )
    if not pairs:
        st.info("現在、統合候補として提示する類似ペアはありません。")
        return

    candidates_by_id = {item.id: item for item in active_candidates}
    pair_keys = [f"{pair.left_id}|{pair.right_id}" for pair in pairs]
    pair_by_key = dict(zip(pair_keys, pairs, strict=True))
    selected_pair_key = st.selectbox(
        "確認する類似ペア",
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
        "主候補（名前・説明・カテゴリの基準）",
        pair_ids,
        format_func=lambda candidate_id: candidates_by_id[candidate_id].candidate.name,
        key="merge_primary_candidate",
    )
    secondary_id = next(candidate_id for candidate_id in pair_ids if candidate_id != primary_id)
    primary = candidates_by_id[primary_id]
    secondary = candidates_by_id[secondary_id]
    st.write(f"類似理由: {', '.join(pair.reasons)}")
    columns = st.columns(2)
    for column, label, saved in (
        (columns[0], "主候補", primary),
        (columns[1], "統合する候補", secondary),
    ):
        with column:
            st.markdown(f"**{label}: {saved.candidate.name}**")
            st.write(saved.candidate.description)
            st.caption(
                f"状態: {saved.status.value} / 引用元: "
                f"{len(saved.candidate.source_references)}件"
            )

    merged = merge_candidate_data(primary.candidate, secondary.candidate)
    with st.expander("統合後の内容を確認", expanded=True):
        st.write(f"候補名: {merged.name}")
        st.write(f"説明: {merged.description}")
        st.write(f"引用元: {len(merged.source_references)}件")
        st.write(f"手順: {len(merged.workflow)}件 / 原則: {len(merged.principles)}件")
        st.caption("統合後は通常の候補レビュー画面で編集してから承認できます。")

    confirmed = st.checkbox(
        "元の2候補を保留にし、統合結果を新しい未確認候補として保存します",
        key=f"confirm_merge_{selected_pair_key}",
    )
    if st.button(
        "未確認候補として統合",
        disabled=not confirmed,
        key=f"merge_candidates_{selected_pair_key}",
    ):
        try:
            repository.create_merged_candidate(primary_id, secondary_id, merged)
        except ValueError as exc:
            st.error(f"候補を統合できません: {exc}")
        else:
            st.success("統合候補を保存し、元の2候補を保留にしました。")
            st.rerun()


def _render_skill_dna(
    candidate_repository: ExtractionRepository,
    skill_repository: SkillDNARepository,
) -> None:
    st.divider()
    st.subheader("4. 承認済み候補をSkill DNA化する")
    st.caption(
        "承認済み候補だけを、別操作でローカルDBへ保存します。"
        "この段階ではSKILL.mdや他のファイルを出力しません。"
    )
    approved_candidates = candidate_repository.list_candidates(
        status=CandidateStatus.APPROVED
    )
    approved = [
        item
        for item in approved_candidates
        if not trace_gate_errors(item.candidate, item.instruction_traces)
    ]
    blocked_count = len(approved_candidates) - len(approved)
    if blocked_count:
        st.warning(
            f"承認済み表示の候補 {blocked_count}件はDNA Trace未完了のため除外しました。"
            "ステップ3で根拠を再確認してください。"
        )
    if not approved:
        st.info("DNA Trace確認済みで、Skill DNAへ変換できる候補はありません。")
        return

    selected_id = st.selectbox(
        "Skill DNA化する承認済み候補",
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
        st.error(f"Skill DNAを準備できません: {exc}")
        return

    columns = st.columns(2)
    with columns[0]:
        st.markdown("**変換前：承認済み候補**")
        st.json(saved.candidate.model_dump(mode="json"))
    with columns[1]:
        st.markdown(f"**変換後：Skill DNA v{preview.version}**")
        st.json(preview.model_dump(mode="json"))

    existing = skill_repository.get_by_candidate(selected_id)
    action = "Skill DNAを更新して新しい版を保存" if existing else "Skill DNAとして保存"
    confirmed = st.checkbox(
        "変換前後を確認し、ローカルDBへ保存します",
        key=f"confirm_skill_dna_{selected_id}",
    )
    if st.button(action, disabled=not confirmed, key=f"save_skill_dna_{selected_id}"):
        try:
            stored = service.convert_approved_candidate(selected_id)
        except ValueError as exc:
            st.error(f"Skill DNAを保存できません: {exc}")
        else:
            st.session_state["skill_dna_notice"] = (
                f"{stored.name} をSkill DNA v{stored.version}として保存しました。"
            )
            st.rerun()

    if notice := st.session_state.pop("skill_dna_notice", None):
        st.success(notice)
    current = skill_repository.get_by_candidate(selected_id)
    if current is not None:
        versions = skill_repository.list_versions(current.id)
        st.caption(
            f"現在版: {current.version} / 保存済み履歴: "
            + ", ".join(item.version for item in versions)
        )


def _render_skill_export(
    skill_repository: SkillDNARepository,
    export_repository: ExportRepository,
) -> None:
    st.divider()
    st.subheader("5. Codex Skillを出力する")
    st.caption(
        "保存済みSkill DNAからSKILL.mdをプレビューし、指定したフォルダの内側だけへ出力します。"
    )
    stored_skills = skill_repository.list_all()
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
        st.warning(
            f"保存済みSkill DNA {blocked_count}件は現行DNA Trace未確認または候補更新後のため"
            "出力対象から除外しました。ステップ3と4で再確認してください。"
        )
    if not skills:
        st.info("現行DNA Traceで確認済みの、出力できるSkill DNAはまだありません。")
        return
    selected_id = st.selectbox(
        "出力するSkill DNA",
        [skill.id for skill in skills],
        format_func=lambda skill_id: next(
            f"{skill.name} v{skill.version}" for skill in skills if skill.id == skill_id
        ),
        key="export_skill_dna_id",
    )
    skill = next(item for item in skills if item.id == selected_id)
    destination = st.text_input(
        "出力先の親フォルダ",
        placeholder=r"例: C:\Users\ユーザー名\.codex\skills",
        key="skill_export_destination",
    ).strip()
    if not destination:
        st.info("既に存在する出力先フォルダを入力すると、保存前プレビューを表示します。")
        return

    service = SkillExportService(export_repository)
    try:
        plan = service.prepare(skill, Path(destination))
    except (OSError, ValueError) as exc:
        st.error(f"出力先を準備できません: {exc}")
        return
    st.write(f"出力予定: `{plan.skill_file}`")
    st.code(plan.content, language="markdown", wrap_lines=True)
    if plan.overwrites_existing:
        st.warning("同じ場所にSKILL.mdが存在します。内容を置き換えるには追加確認が必要です。")
    preview_confirmed = st.checkbox(
        "出力内容と出力先を確認しました",
        key=f"confirm_export_preview_{selected_id}",
    )
    overwrite_confirmed = not plan.overwrites_existing or st.checkbox(
        "既存のSKILL.mdを上書きします",
        key=f"confirm_export_overwrite_{selected_id}",
    )
    if st.button(
        "SKILL.mdを出力",
        disabled=not (preview_confirmed and overwrite_confirmed),
        key=f"export_skill_{selected_id}",
    ):
        try:
            exported = service.export(plan, overwrite=plan.overwrites_existing)
        except (OSError, ValueError) as exc:
            st.error(f"SKILL.mdを出力できません: {exc}")
        else:
            st.success(f"SKILL.mdを出力しました: {exported}")

    history = export_repository.list_for_skill(skill.id)
    if history:
        st.caption(
            "出力履歴: "
            + " / ".join(
                f"v{item.exported_version} → {item.destination_path}" for item in history
            )
        )


def _render_skill_feedback(
    skill_repository: SkillDNARepository,
    feedback_repository: SkillFeedbackRepository,
) -> None:
    st.divider()
    st.subheader("任意: 生成Skillの使用結果を記録する")
    st.caption(
        "記録はこのPCのローカルDBだけに保存され、外部送信やSkillの自動変更は行いません。"
    )
    skills = skill_repository.list_all()
    if not skills:
        st.info("使用結果を記録できるSkill DNAはまだありません。")
        return

    selected_id = st.selectbox(
        "使用結果を記録するSkill",
        [skill.id for skill in skills],
        format_func=lambda skill_id: next(
            f"{skill.name} v{skill.version}" for skill in skills if skill.id == skill_id
        ),
        key="feedback_skill_dna_id",
    )
    skill = next(item for item in skills if item.id == selected_id)
    usage_labels = {
        SkillUsageStatus.NOT_USED: "まだ使っていない",
        SkillUsageStatus.USED_ONCE: "1回使った",
        SkillUsageStatus.REUSED: "複数回再利用した",
    }
    usefulness_labels = {
        SkillUsefulness.NOT_EVALUATED: "まだ評価しない",
        SkillUsefulness.HELPFUL: "役立った",
        SkillUsefulness.PARTLY_HELPFUL: "一部役立った",
        SkillUsefulness.NOT_HELPFUL: "役立たなかった",
    }
    usage_status = st.selectbox(
        "利用状況",
        list(SkillUsageStatus),
        format_func=usage_labels.get,
        key=f"feedback_usage_{selected_id}",
    )
    usefulness = st.selectbox(
        "役立ち度",
        list(SkillUsefulness),
        format_func=usefulness_labels.get,
        key=f"feedback_usefulness_{selected_id}",
    )
    worked_well = st.text_area(
        "良かった点（任意）",
        max_chars=2_000,
        key=f"feedback_worked_well_{selected_id}",
    )
    needs_improvement = st.text_area(
        "改善したい点（任意）",
        max_chars=2_000,
        key=f"feedback_needs_improvement_{selected_id}",
    )
    st.warning("APIキー、メモ本文、パスワード、個人情報は入力しないでください。")
    if st.button("使用結果をローカル保存", key=f"save_feedback_{selected_id}"):
        try:
            feedback_repository.add(
                skill,
                usage_status=usage_status,
                usefulness=usefulness,
                worked_well=worked_well,
                needs_improvement=needs_improvement,
            )
        except ValueError as exc:
            st.error(f"使用結果を保存できません: {exc}")
        else:
            st.success(f"{skill.name} v{skill.version}の使用結果をローカル保存しました。")

    history = feedback_repository.list_for_skill(skill.id)
    if history:
        st.dataframe(
            [
                {
                    "日時": item.created_at.isoformat(timespec="seconds"),
                    "Skill版": item.skill_version,
                    "利用状況": usage_labels[item.usage_status],
                    "役立ち度": usefulness_labels[item.usefulness],
                    "良かった点": item.worked_well,
                    "改善点": item.needs_improvement,
                }
                for item in reversed(history)
            ],
            width="stretch",
            hide_index=True,
        )


def _render_database_controls(database: Database) -> None:
    st.subheader("ローカルデータ保護")
    st.write(f"DBスキーマバージョン: `{database.schema_version}`")
    st.caption(f"バックアップ保存先: `{database.backups.backup_directory}`")
    if notice := st.session_state.pop("database_notice", None):
        st.success(notice)

    if st.button("今すぐDBバックアップを作成"):
        try:
            backup = database.create_backup(reason="manual")
        except (OSError, ValueError) as exc:
            st.error(f"バックアップを作成できません: {exc}")
        else:
            st.success(f"検証済みバックアップを作成しました: {backup.path.name}")

    backups = database.backups.list_backups()
    if inspection_issues := database.backups.list_issues:
        skipped_names = "、".join(issue.path.name for issue in inspection_issues)
        st.warning(
            "検査できないバックアップを復元候補から除外しました。"
            f"ファイルは変更していません: {skipped_names}"
        )
    if not backups:
        st.info("バックアップはまだありません。")
        return
    st.dataframe(
        [
            {
                "ファイル": item.path.name,
                "作成日時": item.created_at.isoformat(timespec="seconds"),
                "サイズ": item.size_bytes,
                "スキーマ": item.schema_version,
                "整合性": "正常" if item.integrity_ok else "破損または読取不能",
            }
            for item in backups
        ],
        width="stretch",
        hide_index=True,
    )
    valid_backups = [item for item in backups if database.backup_is_compatible(item)]
    if not valid_backups:
        st.error("復元可能な正常バックアップがありません。")
        return
    selected_path = st.selectbox(
        "復元するバックアップ",
        [str(item.path) for item in valid_backups],
        format_func=lambda path: Path(path).name,
        key="restore_backup_path",
    )
    st.warning(
        "復元すると現在のDB内容が選択した時点へ戻ります。復元直前のDBは別の安全バックアップへ自動退避します。"
    )
    restore_confirmed = st.checkbox(
        "現在のDBを安全バックアップした上で復元することを確認しました",
        key="restore_database_confirmed",
    )
    if st.button("選択したDBバックアップを復元", disabled=not restore_confirmed):
        try:
            safety = database.restore_backup(Path(selected_path))
        except (OSError, RuntimeError, ValueError) as exc:
            st.error(f"DBを復元できません: {exc}")
        else:
            st.session_state["database_notice"] = (
                "DBを復元しました。復元前の安全バックアップ: " f"{safety.path.name}"
            )
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
    st.subheader("OpenAI APIキー設定")
    st.write(f"OpenAI APIキー: **{'設定済み' if api_key is not None else '未設定'}**")
    st.write(f"AIモデル: `{settings.openai_model}`")
    st.write(f"ローカルDB: `{settings.resolved_database_path}`")

    if settings.environment != "production":
        st.caption("開発版ではGit管理外の`.env.local`からAPIキーを読み込みます。")
        if api_key is None:
            st.warning(
                "実APIを使うには、アプリと同じフォルダのGit管理外`.env.local`へ"
                "`OPENAI_API_KEY=...`を設定してから再起動してください。"
            )
        return

    st.caption(
        "APIキーはWindows Credential Managerへ保存します。DB、生成Skill、ログには保存しません。"
    )
    if error is not None:
        st.error(error)
        st.warning("安全のため、平文ファイルへの代替保存は行いません。")
        return

    input_generation = st.session_state.get("credential_input_generation", 0)
    with st.form(f"credential_api_key_form_{input_generation}", clear_on_submit=True):
        entered_key = st.text_input(
            "OpenAI APIキー",
            type="password",
            value="",
            placeholder="入力内容は画面に再表示されません",
            key=f"credential_api_key_input_{input_generation}",
        )
        save_key = st.form_submit_button(
            "Windows資格情報ストアへ保存",
        )
    if save_key:
        try:
            KeyringCredentialStore().set_api_key(SecretStr(entered_key))
        except (CredentialStoreError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.session_state["credential_input_generation"] = input_generation + 1
            st.session_state["credential_notice"] = (
                "APIキーをWindows資格情報ストアへ保存しました。API通信は行っていません。"
            )
            st.rerun()

    delete_confirmed = st.checkbox(
        "保存済みAPIキーを削除することを確認しました",
        key="credential_delete_confirmed",
        disabled=api_key is None,
    )
    if st.button(
        "Windows資格情報ストアから削除",
        disabled=api_key is None or not delete_confirmed,
    ):
        try:
            deleted = KeyringCredentialStore().delete_api_key()
        except CredentialStoreError as exc:
            st.error(str(exc))
        else:
            st.session_state["credential_notice"] = (
                "保存済みAPIキーを削除しました。" if deleted else "保存済みAPIキーはありません。"
            )
            st.rerun()

    notice = st.session_state.pop("credential_notice", None)
    if notice:
        st.success(notice)


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
        initial_sidebar_state="expanded",
    )
    inject_theme()
    render_local_safety_sidebar(
        __release_label__,
        api_key_configured=openai_api_key is not None,
    )
    render_hero(__release_label__)
    render_workflow()

    st.info("一般公開前の非公開Betaです。データとAI送信はローカルで確認してから実行します。")

    with st.container(border=True):
        st.markdown("### はじめての最短ルート")
        st.markdown(
            """
            1. **メモを選ぶ** — AIへ送る内容と料金上限を確認します。
            2. **見つかったルールを確認する** — 元メモの根拠を見て、使うものだけ承認します。
            3. **Codexへ保存する** — Skillの全文と保存先を確認して出力します。

            途中で分からなくなった候補は、保留のままで安全に終了できます。
            """
        )

    with st.expander("詳しい5ステップを見る", expanded=False):
        st.markdown(
            """
            1. Vaultフォルダを読み込み、AIへ送るメモだけを選びます。
            2. 伏字済みの送信JSONと料金上限を確認してから抽出します。
            3. 出典を見ながら候補を編集し、使う候補だけを承認します。
            4. 承認済み候補の変換前後を確認してSkill DNAへ保存します。
            5. `SKILL.md`全文と出力先を確認し、Codex Skillとして出力します。
            """
        )

    st.subheader("ローカルファースト")
    st.markdown(
        """
        - メモや生成SkillはこのPCに保存します。
        - 選択していないメモをAIへ送りません。
        - Skill候補は人間が承認するまで出力しません。
        """
    )

    with st.container(border=True):
        _render_api_key_settings(settings, openai_api_key, credential_error)

    st.divider()
    assert database.session_factory is not None
    extraction_repository = ExtractionRepository(database.session_factory)
    skill_repository = SkillDNARepository(database.session_factory)
    export_repository = ExportRepository(database.session_factory)
    feedback_repository = SkillFeedbackRepository(database.session_factory)
    with st.container(border=True):
        _render_vault_browser(
            VaultRepository(database.session_factory),
            ExtractionService(extraction_repository),
            settings.max_input_chars,
            openai_api_key,
            settings.openai_model,
            settings.openai_reasoning_effort,
            settings.openai_max_output_tokens,
        )
    with st.container(border=True):
        _render_candidate_review(extraction_repository)
    with st.container(border=True):
        _render_duplicate_review(extraction_repository)
    with st.container(border=True):
        _render_skill_dna(extraction_repository, skill_repository)
    with st.container(border=True):
        _render_skill_export(skill_repository, export_repository)
    with st.container(border=True):
        _render_skill_feedback(skill_repository, feedback_repository)
    with st.container(border=True):
        _render_database_controls(database)


if __name__ == "__main__":
    main()
