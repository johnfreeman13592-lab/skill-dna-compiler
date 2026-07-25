from __future__ import annotations

from dataclasses import dataclass
from textwrap import indent

from skill_dna_compiler.security import SensitiveDataFinding, SensitiveDataScanner
from skill_dna_compiler.ui.i18n import Language, text

MAX_FEEDBACK_FIELD_CHARS = 2_000


@dataclass(frozen=True)
class FirstUseFeedbackReport:
    """A local-only, sanitized Markdown report prepared for manual sharing."""

    markdown: str
    findings: tuple[SensitiveDataFinding, ...]


def _indented_value(value: str, *, not_provided: str) -> str:
    normalized = value.strip().replace("\x00", "")
    return indent(normalized or not_provided, "    ")


def build_first_use_feedback_report(
    *,
    release_label: str,
    language: Language,
    language_label: str,
    outcome: str,
    furthest_step: str,
    main_difficulty: str,
    reuse_intent: str,
    worked_well: str,
    blocked_or_unclear: str,
    repeated_correction: str,
) -> FirstUseFeedbackReport:
    """Build a previewable report without collecting app, Vault, or account state."""

    free_text = (worked_well, blocked_or_unclear, repeated_correction)
    if any(len(value) > MAX_FEEDBACK_FIELD_CHARS for value in free_text):
        raise ValueError(
            f"Feedback fields must be {MAX_FEEDBACK_FIELD_CHARS:,} characters or fewer"
        )

    not_provided = text(language, "first_feedback.report.not_provided")
    fields = (
        ("first_feedback.report.outcome", outcome),
        ("first_feedback.report.step", furthest_step),
        ("first_feedback.report.difficulty", main_difficulty),
        ("first_feedback.report.reuse", reuse_intent),
        ("first_feedback.report.worked", worked_well),
        ("first_feedback.report.blocked", blocked_or_unclear),
        ("first_feedback.report.repeated", repeated_correction),
    )
    sections = "\n\n".join(
        f"## {text(language, key)}\n"
        f"{_indented_value(value, not_provided=not_provided)}"
        for key, value in fields
    )
    privacy_body = _indented_value(
        text(language, "first_feedback.report.privacy_body"),
        not_provided=not_provided,
    )
    raw_report = (
        f"# {text(language, 'first_feedback.report.title')}\n\n"
        f"- {text(language, 'first_feedback.report.version')}: `{release_label}`\n"
        f"- {text(language, 'first_feedback.report.language')}: {language_label}\n"
        f"- {text(language, 'first_feedback.report.automatic')}: "
        f"{text(language, 'first_feedback.report.none')}\n\n"
        f"{sections}\n\n"
        f"## {text(language, 'first_feedback.report.privacy_title')}\n"
        f"{privacy_body}\n"
    )
    scan = SensitiveDataScanner().scan(raw_report)
    return FirstUseFeedbackReport(
        markdown=scan.sanitized_text,
        findings=tuple(scan.findings),
    )
