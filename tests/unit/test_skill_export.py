from pathlib import Path

import pytest
import yaml
from streamlit.testing.v1 import AppTest

import skill_dna_compiler.exporting.service as export_service_module
from skill_dna_compiler.domain import CandidateStatus
from skill_dna_compiler.exporting import SkillExportService, render_skill_md
from skill_dna_compiler.extraction.schemas import ExtractionResult
from skill_dna_compiler.skill_dna import SkillDNAService
from skill_dna_compiler.storage.database import (
    Database,
    SkillCandidateRecord,
    SkillDNARecord,
    SkillDNAVersionRecord,
)
from skill_dna_compiler.storage.repositories import (
    ExportRepository,
    ExtractionRepository,
    SkillDNARepository,
    VaultRepository,
)
from skill_dna_compiler.vault import scan_vault
from tests.trace_helpers import approve_all_candidate_traces


def _approved_skill(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()
    sessions = database.session_factory
    assert sessions is not None
    candidates = ExtractionRepository(sessions)
    skills = SkillDNARepository(sessions)
    vault = tmp_path / "Vault"
    vault.mkdir()
    (vault / "Rules.md").write_text("Inspect existing files", encoding="utf-8")
    vaults = VaultRepository(sessions)
    vault_id = vaults.save_scan(vault, (), scan_vault(vault))
    document_id = vaults.document_ids_for_paths(vault_id, ["Rules.md"])["Rules.md"]
    result = ExtractionResult.model_validate(
        {
            "candidates": [
                {
                    "name": "Inspect first",
                    "description": "Reuse existing files.",
                    "category": "development",
                    "generality": "cross-project",
                    "triggers": ["Changing code"],
                    "do_not_use_when": ["Answering read-only questions"],
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
                    "confidence": 0.9,
                    "confidence_reason": "Direct statement",
                    "warnings": [],
                }
            ]
        }
    )
    run_id = candidates.start_run(model="mock", prompt_version="test-v1")
    candidates.complete_run(run_id, result)
    saved = candidates.list_candidates()[0]
    approve_all_candidate_traces(candidates, saved)
    candidates.set_candidate_status(saved.id, CandidateStatus.APPROVED)
    skill = SkillDNAService(candidates, skills).convert_approved_candidate(saved.id)
    return skill, ExportRepository(sessions)


def test_renderer_is_deterministic_and_has_codex_frontmatter(tmp_path):
    skill, _ = _approved_skill(tmp_path)

    first = render_skill_md(skill)
    second = render_skill_md(skill)

    assert first == second
    frontmatter = yaml.safe_load(first.split("---", 2)[1])
    assert frontmatter.keys() == {"name", "description"}
    assert frontmatter["name"] == "inspect-first"
    assert "Use when Changing code" in frontmatter["description"]
    assert "## Workflow\n\n1. Inspect files" in first
    assert f"`{skill.sources[0].document_id}`" in first
    assert "> Inspect existing files" in first


def test_renderer_normalizes_terminal_punctuation_in_frontmatter(tmp_path):
    skill, _ = _approved_skill(tmp_path)
    skill = skill.model_copy(
        update={
            "triggers": ["A completion record exists.", "Check-only is available;"],
            "do_not_use_when": ["No persisted state exists."],
        }
    )

    rendered = render_skill_md(skill)
    description = yaml.safe_load(rendered.split("---", 2)[1])["description"]

    assert "record exists.;" not in description
    assert "available;." not in description
    assert "Use when A completion record exists; Check-only is available." in description
    assert "Do not use when No persisted state exists." in description


def test_export_requires_explicit_overwrite_and_records_history(tmp_path):
    skill, repository = _approved_skill(tmp_path)
    service = SkillExportService(repository)
    destination = tmp_path / "approved"
    destination.mkdir()

    plan = service.prepare(skill, destination)
    assert plan.overwrites_existing is False
    assert not plan.skill_file.exists()
    exported = service.export(plan)

    assert exported == destination / "inspect-first" / "SKILL.md"
    assert exported.read_text(encoding="utf-8") == plan.content
    assert [item.exported_version for item in repository.list_for_skill(skill.id)] == [
        "0.1.0"
    ]

    existing_plan = service.prepare(skill, destination)
    assert existing_plan.overwrites_existing is True
    with pytest.raises(FileExistsError, match="overwrite"):
        service.export(existing_plan)
    assert len(repository.list_for_skill(skill.id)) == 1

    service.export(existing_plan, overwrite=True)
    assert len(repository.list_for_skill(skill.id)) == 2


def test_export_rejects_symbolic_link_skill_directory(tmp_path):
    skill, repository = _approved_skill(tmp_path)
    destination = tmp_path / "approved"
    outside = tmp_path / "outside"
    destination.mkdir()
    outside.mkdir()
    link = destination / skill.slug
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic links are unavailable in this Windows environment")

    with pytest.raises(ValueError, match="symbolic-link"):
        SkillExportService(repository).prepare(skill, destination)


def test_export_destination_must_exist(tmp_path):
    skill, repository = _approved_skill(tmp_path)

    with pytest.raises(FileNotFoundError):
        SkillExportService(repository).prepare(skill, tmp_path / "missing")


def test_export_plan_rejects_changed_content(tmp_path):
    skill, repository = _approved_skill(tmp_path)
    destination = tmp_path / "approved"
    destination.mkdir()
    service = SkillExportService(repository)
    plan = service.prepare(skill, destination)
    changed = plan.__class__(
        skill_dna=plan.skill_dna,
        approved_root=plan.approved_root,
        skill_directory=plan.skill_directory,
        skill_file=plan.skill_file,
        content=plan.content + "changed",
        overwrites_existing=plan.overwrites_existing,
    )

    with pytest.raises(ValueError, match="preview"):
        service.export(changed)
    assert not list(Path(destination).rglob("SKILL.md"))


def test_export_rejects_skill_that_differs_from_saved_snapshot_before_writing(tmp_path):
    skill, repository = _approved_skill(tmp_path)
    destination = tmp_path / "approved"
    destination.mkdir()
    forged = skill.model_copy(update={"name": "Forged display name"})

    with pytest.raises(ValueError, match="saved normalized record"):
        SkillExportService(repository).prepare(forged, destination)

    assert not list(destination.rglob("SKILL.md"))


def test_export_rejects_tampered_persisted_skill_json_and_snapshot(tmp_path):
    skill, repository = _approved_skill(tmp_path)
    destination = tmp_path / "approved"
    destination.mkdir()
    with repository._sessions() as session:
        record = session.get(SkillDNARecord, skill.id)
        assert record is not None
        tampered = dict(record.skill_data)
        tampered["slug"] = "tampered-slug"
        record.skill_data = tampered
        session.commit()

    with pytest.raises(ValueError, match="saved normalized record"):
        SkillExportService(repository).prepare(skill, destination)
    assert not list(destination.rglob("SKILL.md"))


def test_export_rejects_candidate_source_json_that_differs_from_validated_record(tmp_path):
    skill, repository = _approved_skill(tmp_path)
    destination = tmp_path / "approved"
    destination.mkdir()
    with repository._sessions() as session:
        candidate = session.get(SkillCandidateRecord, skill.candidate_id)
        assert candidate is not None
        candidate_data = dict(candidate.candidate_data)
        sources = [dict(source) for source in candidate_data["source_references"]]
        sources[0]["reason"] = "Tampered reason"
        candidate_data["source_references"] = sources
        candidate.candidate_data = candidate_data
        session.commit()

    with pytest.raises(ValueError, match="validated source records"):
        SkillExportService(repository).prepare(skill, destination)

    assert not list(destination.rglob("SKILL.md"))


def test_export_rejects_legacy_untraced_skill_before_writing(tmp_path):
    skill, repository = _approved_skill(tmp_path)
    destination = tmp_path / "approved"
    destination.mkdir()
    legacy = skill.model_copy(
        update={"trace_policy_version": None, "instruction_traces": []}
    )

    with pytest.raises(ValueError, match="DNA Trace gate failed"):
        SkillExportService(repository).prepare(legacy, destination)

    assert not list(destination.rglob("SKILL.md"))

    with repository._sessions() as session:
        record = session.get(SkillDNARecord, skill.id)
        assert record is not None
        record.skill_data = skill.model_dump(mode="json")
        snapshot = session.query(SkillDNAVersionRecord).filter_by(
            skill_dna_id=skill.id, version=skill.version
        ).one()
        tampered_snapshot = dict(snapshot.skill_data)
        tampered_snapshot["version"] = "9.9.9"
        snapshot.skill_data = tampered_snapshot
        session.commit()

    with pytest.raises(ValueError, match="immutable version snapshot"):
        SkillExportService(repository).prepare(skill, destination)
    assert not list(destination.rglob("SKILL.md"))


def test_export_history_failure_rolls_back_new_file_and_directory(tmp_path, monkeypatch):
    skill, repository = _approved_skill(tmp_path)
    destination = tmp_path / "approved"
    destination.mkdir()
    service = SkillExportService(repository)
    plan = service.prepare(skill, destination)
    monkeypatch.setattr(
        repository,
        "record_export",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("DB unavailable")),
    )

    with pytest.raises(RuntimeError, match="DB unavailable"):
        service.export(plan)

    assert not plan.skill_file.exists()
    assert not plan.skill_directory.exists()
    assert repository.list_for_skill(skill.id) == []


def test_export_history_failure_restores_existing_file(tmp_path, monkeypatch):
    skill, repository = _approved_skill(tmp_path)
    destination = tmp_path / "approved"
    destination.mkdir()
    skill_directory = destination / skill.slug
    skill_directory.mkdir()
    existing = skill_directory / "SKILL.md"
    existing.write_text("original content\n", encoding="utf-8")
    service = SkillExportService(repository)
    plan = service.prepare(skill, destination)
    monkeypatch.setattr(
        repository,
        "record_export",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("DB unavailable")),
    )

    with pytest.raises(RuntimeError, match="DB unavailable"):
        service.export(plan, overwrite=True)

    assert existing.read_text(encoding="utf-8") == "original content\n"
    assert repository.list_for_skill(skill.id) == []


def test_export_reports_explicit_failure_when_file_rollback_also_fails(
    tmp_path, monkeypatch
):
    skill, repository = _approved_skill(tmp_path)
    destination = tmp_path / "approved"
    destination.mkdir()
    skill_directory = destination / skill.slug
    skill_directory.mkdir()
    existing = skill_directory / "SKILL.md"
    existing.write_text("original content\n", encoding="utf-8")
    service = SkillExportService(repository)
    plan = service.prepare(skill, destination)
    monkeypatch.setattr(
        repository,
        "record_export",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("DB unavailable")),
    )
    real_atomic_replace = export_service_module._atomic_replace_bytes
    replace_calls = 0

    def fail_restore(destination_path, content):
        nonlocal replace_calls
        replace_calls += 1
        if replace_calls == 2:
            raise OSError("synthetic rollback denial")
        real_atomic_replace(destination_path, content)

    monkeypatch.setattr(export_service_module, "_atomic_replace_bytes", fail_restore)

    with pytest.raises(RuntimeError, match="could not be restored") as failure:
        service.export(plan, overwrite=True)

    assert isinstance(failure.value.__cause__, OSError)
    assert "synthetic rollback denial" in str(failure.value.__cause__)
    assert existing.read_text(encoding="utf-8") == plan.content
    assert repository.list_for_skill(skill.id) == []


def test_export_rejects_stale_skill_after_candidate_is_edited_and_reapproved(tmp_path):
    skill, repository = _approved_skill(tmp_path)
    candidates = ExtractionRepository(repository._sessions)
    saved = candidates.get_candidate(skill.candidate_id)
    edited = saved.candidate.model_copy(update={"name": "Updated candidate name"})
    updated = candidates.update_candidate(saved.id, edited)
    approve_all_candidate_traces(candidates, updated)
    candidates.set_candidate_status(saved.id, CandidateStatus.APPROVED)
    destination = tmp_path / "approved"
    destination.mkdir()

    with pytest.raises(ValueError, match="older than|differs"):
        SkillExportService(repository).prepare(skill, destination)

    assert not list(destination.rglob("SKILL.md"))


def test_app_previews_and_explicitly_exports_skill(tmp_path, monkeypatch):
    skill, _ = _approved_skill(tmp_path)
    destination = tmp_path / "codex-skills"
    destination.mkdir()
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "test.db"))
    app = AppTest.from_file("app.py").run(timeout=30)
    assert next(
        button for button in app.button if button.label == "4. Save and use"
    ).disabled
    next(button for button in app.button if button.label == "Settings").click()
    app.run(timeout=30)
    next(
        widget
        for widget in app.selectbox
        if widget.label == "Saved Skill to inspect"
    ).set_value(skill.id)
    app.run(timeout=30)
    next(button for button in app.button if button.label == "Resume from this Skill").click()
    app.run(timeout=30)

    next(
        widget for widget in app.text_input if widget.label == "Parent destination folder"
    ).set_value(str(destination))
    app.run(timeout=30)

    assert any(str(destination / skill.slug / "SKILL.md") in item.value for item in app.markdown)
    assert any("name: inspect-first" in item.value for item in app.code)
    export_button = next(
        button for button in app.button if button.label == "Export `SKILL.md`"
    )
    assert export_button.disabled is True
    next(
        checkbox
        for checkbox in app.checkbox
        if checkbox.label == "I reviewed the complete content and destination"
    ).set_value(True)
    app.run(timeout=30)
    next(
        button for button in app.button if button.label == "Export `SKILL.md`"
    ).click()
    app.run(timeout=30)

    exported = destination / skill.slug / "SKILL.md"
    assert exported.is_file()
    assert not app.exception
    assert any("Exported `SKILL.md`" in item.value for item in app.success)
