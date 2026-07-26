"""Presentation helpers for the local Streamlit interface."""

from .feedback_report import (
    MAX_FEEDBACK_FIELD_CHARS,
    FirstUseFeedbackReport,
    build_first_use_feedback_report,
)
from .guided_walkthrough import (
    build_guided_walkthrough_data_uri,
    build_guided_walkthrough_html,
)
from .i18n import DEFAULT_LANGUAGE, LANGUAGE_LABELS, Language, text
from .theme import inject_theme, render_hero, render_local_safety_sidebar, render_workflow

__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGE_LABELS",
    "MAX_FEEDBACK_FIELD_CHARS",
    "FirstUseFeedbackReport",
    "Language",
    "build_first_use_feedback_report",
    "build_guided_walkthrough_data_uri",
    "build_guided_walkthrough_html",
    "inject_theme",
    "render_hero",
    "render_local_safety_sidebar",
    "render_workflow",
    "text",
]
