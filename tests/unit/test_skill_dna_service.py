import pytest

from skill_dna_compiler.domain import CandidateStatus
from skill_dna_compiler.extraction.schemas import ExtractionResult
from skill_dna_compiler.skill_dna import SkillDNAService, suggest_slug
from skill_dna_compiler.storage.database import Database, SkillCandidateRecord
from skill_dna_compiler.storage.repositories import (
    ExtractionRepository,
    SkillDNARepository,
    VaultRepository,
)
from skill_dna_compiler.vault import scan_vault
from tests.trace_helpers import approve_all_candidate_traces


def _setup(tmp_path):
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
    return candidates, skills, SkillDNAService(candidates, skills), saved


@pytest.mark.parametrize(
    "status",
    [CandidateStatus.PENDING, CandidateStatus.ON_HOLD, CandidateStatus.REJECTED],
)
def test_only_approved_candidate_can_be_converted(tmp_path, status):
    candidates, skills, service, saved = _setup(tmp_path)
    candidates.set_candidate_status(saved.id, status)

    with pytest.raises(ValueError, match="approved"):
        service.convert_approved_candidate(saved.id)

    assert skills.list_all() == []
    assert list(tmp_path.rglob("SKILL.md")) == []


def test_approved_candidate_is_preserved_as_versioned_skill_dna(tmp_path):
    candidates, skills, service, saved = _setup(tmp_path)
    approve_all_candidate_traces(candidates, saved)
    candidates.set_candidate_status(saved.id, CandidateStatus.APPROVED)

    preview = service.preview_approved_candidate(saved.id)
    assert preview.version == "0.1.0"
    assert skills.list_all() == []
    dna = service.convert_approved_candidate(saved.id)

    source = saved.candidate
    assert dna.version == "0.1.0"
    assert dna.name == source.name
    assert dna.description == source.description
    assert dna.triggers == source.triggers
    assert dna.do_not_use_when == source.do_not_use_when
    assert dna.principles == source.principles
    assert dna.workflow == source.workflow
    assert dna.constraints == source.constraints
    assert dna.sources[0].document_id == source.source_references[0].document_id
    assert dna.sources[0].quote == source.source_references[0].quote
    assert [item.version for item in skills.list_versions(dna.id)] == ["0.1.0"]
    assert list(tmp_path.rglob("SKILL.md")) == []

    forged = dna.model_copy(update={"name": "Forged Skill DNA"})
    with pytest.raises(ValueError, match="older than|differs"):
        skills.save_version(forged)

    edited = source.model_copy(update={"description": "Review before editing."})
    edited_saved = candidates.update_candidate(saved.id, edited)
    approve_all_candidate_traces(candidates, edited_saved)
    candidates.set_candidate_status(saved.id, CandidateStatus.APPROVED)
    updated = service.convert_approved_candidate(saved.id)

    assert updated.id == dna.id
    assert updated.slug == dna.slug
    assert updated.version == "0.1.1"
    assert updated.description == "Review before editing."
    versions = skills.list_versions(dna.id)
    assert [item.version for item in versions] == ["0.1.0", "0.1.1"]
    assert versions[0].skill_dna.description == "Reuse existing files."


def test_legacy_approved_candidate_without_traces_cannot_be_converted(tmp_path):
    candidates, skills, service, saved = _setup(tmp_path)
    with candidates._sessions() as session:
        record = session.get(SkillCandidateRecord, saved.id)
        assert record is not None
        record.status = CandidateStatus.APPROVED.value
        session.commit()

    with pytest.raises(ValueError, match="DNA Trace gate failed"):
        service.convert_approved_candidate(saved.id)

    assert skills.list_all() == []


def test_slug_is_safe_for_ascii_and_japanese_names():
    assert suggest_slug("Inspect Existing Files!", "candidate_123") == (
        "inspect-existing-files"
    )
    assert suggest_slug("安全な手順", "candidate_ABC123") == "skill-didateabc123"
