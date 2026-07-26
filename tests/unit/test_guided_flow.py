from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from streamlit.testing.v1 import AppTest

from app import (
    GuidedEligibility,
    GuidedView,
    guided_view_is_eligible,
    note_selection_is_current,
    resolve_guided_view,
)
from skill_dna_compiler.config.settings import get_settings
from skill_dna_compiler.ui import text
from skill_dna_compiler.vault import VaultFile
from tests.unit.test_skill_export import _approved_skill


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_guided_view_eligibility_and_stale_fallback_are_deterministic():
    empty = GuidedEligibility()
    notes = GuidedEligibility(notes_selected=True)
    drafts = GuidedEligibility(notes_selected=True, draft_available=True)
    approved = GuidedEligibility(
        notes_selected=True,
        draft_available=True,
        approved_candidate=True,
    )

    assert guided_view_is_eligible(GuidedView.NOTES, empty)
    assert not guided_view_is_eligible(GuidedView.DATA, empty)
    assert resolve_guided_view(GuidedView.SAVE, empty) is GuidedView.NOTES
    assert resolve_guided_view(GuidedView.SAVE, notes) is GuidedView.DATA
    assert resolve_guided_view(GuidedView.SAVE, drafts) is GuidedView.REVIEW
    assert resolve_guided_view(GuidedView.SAVE, approved) is GuidedView.SAVE
    assert resolve_guided_view("not-a-view", approved) is GuidedView.HOME


def test_note_selection_must_belong_to_current_loaded_vault():
    files = cast(
        list[VaultFile],
        [
            SimpleNamespace(relative_path="safe.md"),
            SimpleNamespace(relative_path="testing.md"),
        ],
    )

    assert note_selection_is_current(files, ["safe.md"], "vault-1")
    assert not note_selection_is_current(files, [], "vault-1")
    assert not note_selection_is_current(files, ["outside.md"], "vault-1")
    assert not note_selection_is_current(files, ["safe.md"], None)


def test_app_starts_at_home_then_routes_to_note_selection(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "guided.db"))
    app = AppTest.from_file("app.py").run(timeout=30)

    assert not app.exception
    assert any(
        item.value == "Turn your notes into instructions your AI can reuse."
        for item in app.title
    )
    assert any(button.label == "Try the sample" for button in app.button)
    assert any(button.label == "Use my notes" for button in app.button)
    assert not any(widget.label == "Vault folder" for widget in app.text_input)

    next(button for button in app.button if button.label == "Use my notes").click()
    app.run(timeout=30)

    assert not app.exception
    assert any(item.value == "Choose the notes to use" for item in app.title)
    assert any(widget.label == "Vault folder" for widget in app.text_input)
    assert next(
        button for button in app.button if button.label == "2. Check data"
    ).disabled


def _run_english_mock_journey(app: AppTest, vault: Path) -> AppTest:
    next(button for button in app.button if button.label == "Use my notes").click()
    app.run(timeout=30)
    next(widget for widget in app.text_input if widget.label == "Vault folder").set_value(
        str(vault)
    )
    next(button for button in app.button if button.label == "Load Vault").click()
    app.run(timeout=30)
    next(
        widget
        for widget in app.multiselect
        if widget.label == "Notes to analyze (not sent yet)"
    ).set_value(["Rule.md"])
    app.run(timeout=30)
    next(
        button for button in app.button if button.label == "Continue to data review"
    ).click()
    app.run(timeout=30)
    next(
        button for button in app.button if button.label == "Prepare outbound content"
    ).click()
    app.run(timeout=30)
    next(
        checkbox
        for checkbox in app.checkbox
        if checkbox.label == "I reviewed the redacted outbound content"
    ).set_value(True)
    app.run(timeout=30)
    next(button for button in app.button if button.label == "Run mock extraction").click()
    return app.run(timeout=30)


def test_persisted_history_does_not_enable_current_review_or_save(tmp_path, monkeypatch):
    skill, _ = _approved_skill(tmp_path)
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "test.db"))
    app = AppTest.from_file("app.py").run(timeout=30)

    assert next(
        button for button in app.button if button.label == "3. Review draft"
    ).disabled
    assert next(
        button for button in app.button if button.label == "4. Save and use"
    ).disabled

    app.session_state["guided_view"] = "review"
    app.run(timeout=30)
    assert any(item.value == "Choose the notes to use" for item in app.title)

    next(button for button in app.button if button.label == "Settings").click()
    app.run(timeout=30)
    history = next(
        widget
        for widget in app.selectbox
        if widget.label == "Past draft to inspect"
    )
    assert history.value is None
    history.set_value(skill.candidate_id)
    app.run(timeout=30)
    next(button for button in app.button if button.label == "Resume this draft").click()
    app.run(timeout=30)

    assert any(item.value == "Check each draft against your notes" for item in app.title)
    assert next(
        button for button in app.button if button.label == "4. Save and use"
    ).disabled is False
    next(
        widget for widget in app.text_input if widget.label == "Candidate name"
    ).set_value("Inspect first, revised")
    next(button for button in app.button if button.label == "Save edits").click()
    app.run(timeout=30)
    assert "current_approved_candidate_id" not in app.session_state.filtered_state
    assert next(
        button for button in app.button if button.label == "4. Save and use"
    ).disabled


def test_note_change_invalidates_current_journey_and_consents(tmp_path, monkeypatch):
    vault = tmp_path / "Vault"
    vault.mkdir()
    (vault / "Rule.md").write_text("Back up before changing data.", encoding="utf-8")
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "guided.db"))
    app = _run_english_mock_journey(
        AppTest.from_file("app.py").run(timeout=30),
        vault,
    )

    assert app.session_state.filtered_state["current_run_id"].startswith("run_")
    assert app.session_state.filtered_state["payload_confirmed"] is True
    next(button for button in app.button if button.label == "1. Choose notes").click()
    app.run(timeout=30)
    next(
        widget
        for widget in app.multiselect
        if widget.label == "Notes to analyze (not sent yet)"
    ).set_value([])
    app.run(timeout=30)

    state = app.session_state.filtered_state
    assert "current_run_id" not in state
    assert "current_candidate_ids" not in state
    assert "current_approved_candidate_id" not in state
    assert "prepared_payload" not in state
    assert state.get("payload_confirmed") in (None, False)
    assert state.get("cost_confirmed") in (None, False)
    assert next(
        button for button in app.button if button.label == "2. Check data"
    ).disabled
    assert next(
        button for button in app.button if button.label == "3. Review draft"
    ).disabled


def test_payload_change_falls_back_and_invalidates_current_markers(tmp_path, monkeypatch):
    vault = tmp_path / "Vault"
    vault.mkdir()
    (vault / "Rule.md").write_text("Back up before changing data.", encoding="utf-8")
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "guided.db"))
    app = _run_english_mock_journey(
        AppTest.from_file("app.py").run(timeout=30),
        vault,
    )

    prepared = app.session_state.filtered_state["prepared_payload"]
    app.session_state["prepared_payload"] = replace(
        prepared,
        serialized_json=f"{prepared.serialized_json} ",
    )
    app.session_state["guided_view"] = "review"
    app.run(timeout=30)

    assert any(
        item.value == "Check the data before creating drafts" for item in app.title
    )
    state = app.session_state.filtered_state
    assert "current_run_id" not in state
    assert "current_candidate_ids" not in state
    assert state.get("payload_confirmed") in (None, False)
    assert state.get("cost_confirmed") in (None, False)


def test_model_contract_change_invalidates_current_markers(tmp_path, monkeypatch):
    vault = tmp_path / "Vault"
    vault.mkdir()
    (vault / "Rule.md").write_text("Back up before changing data.", encoding="utf-8")
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "guided.db"))
    app = _run_english_mock_journey(
        AppTest.from_file("app.py").run(timeout=30),
        vault,
    )

    app.session_state["guided_runtime_extraction_config"] = (
        "changed-model",
        "changed-effort",
        1,
    )
    app.session_state["guided_view"] = "review"
    app.run(timeout=30)

    state = app.session_state.filtered_state
    assert "current_run_id" not in state
    assert "current_candidate_ids" not in state
    assert state.get("payload_confirmed") in (None, False)
    assert state.get("cost_confirmed") in (None, False)
    assert any(
        item.value == "Check the data before creating drafts" for item in app.title
    )


def test_english_and_japanese_copy_cover_all_four_routes():
    steps = ("notes", "data", "review", "save")
    assert [text("en", f"guided.step.{step}.title") for step in steps] == [
        "Choose the notes to use",
        "Check the data before creating drafts",
        "Check each draft against your notes",
        "Save the Skill, then save the file",
    ]
    assert [text("ja", f"guided.step.{step}.title") for step in steps] == [
        "使用するメモを選ぶ",
        "Skill案を作る前にデータを確認",
        "Skill案を元メモと照らし合わせる",
        "Skillを保存してからファイルを保存",
    ]


def test_japanese_app_routes_notes_data_and_review(tmp_path, monkeypatch):
    vault = tmp_path / "Vault"
    vault.mkdir()
    (vault / "Rule.md").write_text("変更前にバックアップする。", encoding="utf-8")
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "guided-ja.db"))
    app = AppTest.from_file("app.py").run(timeout=30)
    next(widget for widget in app.selectbox if widget.label == "Language").set_value("ja")
    app.run(timeout=30)

    next(
        button
        for button in app.button
        if button.label == text("ja", "guided.home.own")
    ).click()
    app.run(timeout=30)
    assert any(
        item.value == text("ja", "guided.step.notes.title") for item in app.title
    )
    next(
        widget
        for widget in app.text_input
        if widget.label == text("ja", "vault.path")
    ).set_value(str(vault))
    next(
        button for button in app.button if button.label == text("ja", "vault.load")
    ).click()
    app.run(timeout=30)
    next(
        widget
        for widget in app.multiselect
        if widget.label == text("ja", "vault.analysis_selection")
    ).set_value(["Rule.md"])
    app.run(timeout=30)
    next(
        button
        for button in app.button
        if button.label == text("ja", "guided.continue.data")
    ).click()
    app.run(timeout=30)
    assert any(
        item.value == text("ja", "guided.step.data.title") for item in app.title
    )
    next(
        button
        for button in app.button
        if button.label == text("ja", "payload.prepare")
    ).click()
    app.run(timeout=30)
    next(
        checkbox
        for checkbox in app.checkbox
        if checkbox.label == text("ja", "payload.confirm")
    ).set_value(True)
    app.run(timeout=30)
    next(
        button
        for button in app.button
        if button.label == text("ja", "extract.mock")
    ).click()
    app.run(timeout=30)
    next(
        button
        for button in app.button
        if button.label == text("ja", "guided.continue.review")
    ).click()
    app.run(timeout=30)
    assert any(
        item.value == text("ja", "guided.step.review.title") for item in app.title
    )


def test_japanese_explicit_history_resume_routes_to_save(tmp_path, monkeypatch):
    skill, _ = _approved_skill(tmp_path)
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "test.db"))
    app = AppTest.from_file("app.py").run(timeout=30)
    next(widget for widget in app.selectbox if widget.label == "Language").set_value("ja")
    app.run(timeout=30)

    next(
        button
        for button in app.button
        if button.label == text("ja", "guided.nav.settings")
    ).click()
    app.run(timeout=30)
    next(
        widget
        for widget in app.selectbox
        if widget.label == text("ja", "guided.history.skill")
    ).set_value(skill.id)
    app.run(timeout=30)
    next(
        button
        for button in app.button
        if button.label == text("ja", "guided.history.resume_skill")
    ).click()
    app.run(timeout=30)

    assert any(
        item.value == text("ja", "guided.step.save.title") for item in app.title
    )
