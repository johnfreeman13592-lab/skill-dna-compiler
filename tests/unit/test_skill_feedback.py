import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

from skill_dna_compiler.config.settings import get_settings
from skill_dna_compiler.domain import (
    CandidateStatus,
    SkillUsageStatus,
    SkillUsefulness,
)
from skill_dna_compiler.extraction.schemas import ExtractionResult
from skill_dna_compiler.skill_dna import SkillDNAService
from skill_dna_compiler.storage.database import Database
from skill_dna_compiler.storage.repositories import (
    ExtractionRepository,
    SkillDNARepository,
    SkillFeedbackRepository,
    VaultRepository,
)
from skill_dna_compiler.vault import scan_vault
from tests.trace_helpers import approve_all_candidate_traces


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _create_skill(database_path, tmp_path):
    database = Database(database_path)
    database.initialize()
    sessions = database.session_factory
    assert sessions is not None
    candidates = ExtractionRepository(sessions)
    skills = SkillDNARepository(sessions)
    vault = tmp_path / "FeedbackVault"
    vault.mkdir(exist_ok=True)
    (vault / "Rule.md").write_text("Inspect existing files", encoding="utf-8")
    vaults = VaultRepository(sessions)
    vault_id = vaults.save_scan(vault, (), scan_vault(vault))
    document_id = vaults.document_ids_for_paths(vault_id, ["Rule.md"])["Rule.md"]
    result = ExtractionResult.model_validate(
        {
            "candidates": [
                {
                    "name": "Inspect First",
                    "description": "Inspect existing files before editing.",
                    "category": "development",
                    "generality": "cross-project",
                    "triggers": ["Changing code"],
                    "do_not_use_when": ["Read-only questions"],
                    "principles": ["Prefer reuse"],
                    "workflow": [{"order": 1, "action": "Inspect files"}],
                    "constraints": ["Run tests"],
                    "source_references": [
                        {
                            "document_id": document_id,
                            "quote": "Inspect existing files",
                            "reason": "Direct rule",
                        }
                    ],
                    "confidence": 1.0,
                    "confidence_reason": "Test fixture",
                    "warnings": [],
                }
            ]
        }
    )
    run_id = candidates.start_run(model="mock", prompt_version="feedback-test-v1")
    candidates.complete_run(run_id, result)
    candidate = candidates.list_candidates()[0]
    approve_all_candidate_traces(candidates, candidate)
    candidates.set_candidate_status(candidate.id, CandidateStatus.APPROVED)
    skill = SkillDNAService(candidates, skills).convert_approved_candidate(candidate.id)
    return database, skill


def test_feedback_is_local_append_only_and_versioned(tmp_path):
    database, skill = _create_skill(tmp_path / "feedback.db", tmp_path)
    assert database.session_factory is not None
    repository = SkillFeedbackRepository(database.session_factory)

    saved = repository.add(
        skill,
        usage_status=SkillUsageStatus.REUSED,
        usefulness=SkillUsefulness.HELPFUL,
        worked_well="  Reduced repeated setup  ",
        needs_improvement="  Add one edge case  ",
    )

    assert saved.skill_version == "0.1.0"
    assert saved.usage_status is SkillUsageStatus.REUSED
    assert saved.usefulness is SkillUsefulness.HELPFUL
    assert saved.worked_well == "Reduced repeated setup"
    assert saved.needs_improvement == "Add one edge case"
    history = repository.list_for_skill(skill.id)
    assert len(history) == 1
    assert history[0].id == saved.id
    assert history[0].skill_version == saved.skill_version
    assert history[0].usage_status is saved.usage_status
    assert history[0].usefulness is saved.usefulness
    assert history[0].worked_well == saved.worked_well
    assert history[0].needs_improvement == saved.needs_improvement
    assert not list(tmp_path.rglob("SKILL.md"))


def test_feedback_rejects_overlong_free_text(tmp_path):
    database, skill = _create_skill(tmp_path / "feedback.db", tmp_path)
    assert database.session_factory is not None
    repository = SkillFeedbackRepository(database.session_factory)

    with pytest.raises(ValueError, match="2,000"):
        repository.add(
            skill,
            usage_status=SkillUsageStatus.USED_ONCE,
            usefulness=SkillUsefulness.PARTLY_HELPFUL,
            worked_well="x" * 2_001,
        )

    assert repository.list_for_skill(skill.id) == []


def test_app_saves_feedback_without_running_extraction(tmp_path, monkeypatch):
    database_path = tmp_path / "feedback.db"
    _, skill = _create_skill(database_path, tmp_path)
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(database_path))
    app = AppTest.from_file("app.py").run(timeout=30)

    next(widget for widget in app.selectbox if widget.label == "Usage").set_value(
        SkillUsageStatus.REUSED
    )
    next(widget for widget in app.selectbox if widget.label == "Usefulness").set_value(
        SkillUsefulness.HELPFUL
    )
    next(
        widget for widget in app.text_area if widget.label == "What worked well (optional)"
    ).set_value(
        "Repeated setup was faster"
    )
    next(
        widget
        for widget in app.text_area
        if widget.label == "What should improve (optional)"
    ).set_value("Clarify one edge case")
    app.run(timeout=30)
    next(
        button for button in app.button if button.label == "Save feedback locally"
    ).click()
    app.run(timeout=30)

    assert not app.exception
    assert any("Saved local feedback" in item.value for item in app.success)
    assert any("API key" in item.value for item in app.warning)
    with sqlite3.connect(database_path) as connection:
        feedback = connection.execute(
            "SELECT skill_dna_id, skill_version, usage_status, usefulness, "
            "worked_well, needs_improvement FROM skill_feedback"
        ).fetchone()
        extraction_count = connection.execute(
            "SELECT COUNT(*) FROM extraction_runs"
        ).fetchone()
    assert feedback == (
        skill.id,
        "0.1.0",
        "reused",
        "helpful",
        "Repeated setup was faster",
        "Clarify one edge case",
    )
    assert extraction_count == (1,)
