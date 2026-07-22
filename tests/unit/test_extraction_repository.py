import pytest
from sqlalchemy import select

from skill_dna_compiler.domain import CandidateStatus
from skill_dna_compiler.extraction.schemas import ExtractedCandidate, ExtractionResult
from skill_dna_compiler.storage.database import (
    Database,
    ExtractionRunRecord,
    SkillCandidateRecord,
    SourceReferenceRecord,
)
from skill_dna_compiler.storage.repositories import ExtractionRepository, VaultRepository
from skill_dna_compiler.vault import scan_vault
from tests.trace_helpers import approve_all_candidate_traces


def _repository(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()
    assert database.session_factory is not None
    return ExtractionRepository(database.session_factory), database.session_factory


def test_complete_run_persists_final_state_without_payload(tmp_path):
    repository, sessions = _repository(tmp_path)
    run_id = repository.start_run(model="mock", prompt_version="test-v1")

    repository.complete_run(run_id, ExtractionResult(candidates=[]))

    with sessions() as session:
        run = session.get(ExtractionRunRecord, run_id)
        assert run is not None
        assert run.status == "completed"
        assert run.completed_at is not None
        assert run.error_message is None
        assert session.scalars(select(SkillCandidateRecord)).all() == []


def test_complete_run_persists_validated_candidate_data(tmp_path):
    repository, sessions = _repository(tmp_path)
    vault = tmp_path / "Vault"
    vault.mkdir()
    (vault / "Rules.md").write_text("Inspect existing files", encoding="utf-8")
    vault_repository = VaultRepository(sessions)
    vault_id = vault_repository.save_scan(vault, (), scan_vault(vault))
    document_id = vault_repository.document_ids_for_paths(vault_id, ["Rules.md"])[
        "Rules.md"
    ]
    run_id = repository.start_run(model="mock", prompt_version="test-v1")
    result = ExtractionResult.model_validate(
        {
            "candidates": [
                {
                    "name": "Inspect first",
                    "description": "Reuse existing files.",
                    "category": "development",
                    "generality": "cross-project",
                    "triggers": ["Starting work"],
                    "do_not_use_when": [],
                    "principles": ["Prefer reuse"],
                    "workflow": [{"order": 1, "action": "Inspect files"}],
                    "constraints": [],
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

    repository.complete_run(run_id, result)

    with sessions() as session:
        candidate = session.scalars(select(SkillCandidateRecord)).one()
        assert candidate.extraction_run_id == run_id
        assert candidate.name == "Inspect first"
        assert candidate.candidate_data["source_references"][0]["document_id"] == document_id
        source = session.scalars(select(SourceReferenceRecord)).one()
        assert source.candidate_id == candidate.id
        assert source.document_id == document_id
        assert source.excerpt == "Inspect existing files"

    saved = repository.list_candidates()
    assert len(saved) == 1
    assert saved[0].status is CandidateStatus.PENDING

    edited = saved[0].candidate.model_copy(
        update={"name": "Inspect before changing", "description": "Review first."}
    )
    updated = repository.update_candidate(saved[0].id, edited)
    assert updated.candidate.name == "Inspect before changing"
    assert updated.status is CandidateStatus.PENDING

    approve_all_candidate_traces(repository, updated)
    approved = repository.set_candidate_status(
        saved[0].id, CandidateStatus.APPROVED
    )
    assert approved.status is CandidateStatus.APPROVED
    assert repository.list_candidates(status=CandidateStatus.PENDING) == []
    assert repository.list_candidates(status=CandidateStatus.APPROVED)[0].id == saved[0].id

    edited_again = approved.candidate.model_copy(update={"description": "Changed."})
    assert repository.update_candidate(saved[0].id, edited_again).status is CandidateStatus.PENDING


def test_candidate_review_cannot_replace_source_references(tmp_path):
    repository, sessions = _repository(tmp_path)
    vault = tmp_path / "Vault"
    vault.mkdir()
    (vault / "Rules.md").write_text("Inspect existing files", encoding="utf-8")
    vault_repository = VaultRepository(sessions)
    vault_id = vault_repository.save_scan(vault, (), scan_vault(vault))
    document_id = vault_repository.document_ids_for_paths(vault_id, ["Rules.md"])[
        "Rules.md"
    ]
    run_id = repository.start_run(model="mock", prompt_version="test-v1")
    candidate = ExtractedCandidate.model_validate(
        {
            "name": "Inspect first",
            "description": "Reuse existing files.",
            "category": "development",
            "generality": "cross-project",
            "triggers": [],
            "do_not_use_when": [],
            "principles": [],
            "workflow": [],
            "constraints": [],
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
    )
    repository.complete_run(run_id, ExtractionResult(candidates=[candidate]))
    saved = repository.list_candidates()[0]
    changed_source = saved.candidate.source_references[0].model_copy(
        update={"quote": "Different quote"}
    )
    changed = saved.candidate.model_copy(update={"source_references": [changed_source]})

    with pytest.raises(ValueError, match="Source references cannot be changed"):
        repository.update_candidate(saved.id, changed)


def test_fail_run_persists_only_safe_message(tmp_path):
    repository, sessions = _repository(tmp_path)
    run_id = repository.start_run(model="mock", prompt_version="test-v1")

    repository.fail_run(run_id, safe_message="Safe retry message")

    with sessions() as session:
        run = session.get(ExtractionRunRecord, run_id)
        assert run is not None
        assert run.status == "failed"
        assert run.error_message == "Safe retry message"


def test_finalized_run_cannot_be_completed_twice(tmp_path):
    repository, _ = _repository(tmp_path)
    run_id = repository.start_run(model="mock", prompt_version="test-v1")
    repository.complete_run(run_id, ExtractionResult(candidates=[]))

    try:
        repository.complete_run(run_id, ExtractionResult(candidates=[]))
    except ValueError as exc:
        assert "already finalized" in str(exc)
    else:
        raise AssertionError("Expected finalized run to be rejected")
