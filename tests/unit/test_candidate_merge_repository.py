import pytest
from sqlalchemy import select

from skill_dna_compiler.domain import CandidateStatus
from skill_dna_compiler.extraction.schemas import ExtractedCandidate, ExtractionResult
from skill_dna_compiler.review import merge_candidate_data
from skill_dna_compiler.storage.database import (
    CandidateMergeSourceRecord,
    Database,
    SkillDNARecord,
    SourceReferenceRecord,
)
from skill_dna_compiler.storage.repositories import ExtractionRepository, VaultRepository
from skill_dna_compiler.vault import scan_vault


def _candidate(name: str, document_id: str, quote: str) -> ExtractedCandidate:
    return ExtractedCandidate.model_validate(
        {
            "name": name,
            "description": "Inspect existing work before changing it.",
            "category": "development",
            "generality": "cross-project",
            "triggers": ["Starting development"],
            "do_not_use_when": [],
            "principles": ["Prefer reuse"],
            "workflow": [{"order": 1, "action": "Inspect files"}],
            "constraints": [],
            "source_references": [
                {
                    "document_id": document_id,
                    "quote": quote,
                    "reason": "Direct rule",
                }
            ],
            "confidence": 0.9,
            "confidence_reason": "Direct statement",
            "warnings": [],
        }
    )


def test_manual_merge_is_auditable_and_keeps_skill_generation_separate(tmp_path):
    vault = tmp_path / "Vault"
    vault.mkdir()
    (vault / "First.md").write_text("Inspect existing files", encoding="utf-8")
    (vault / "Second.md").write_text("Review existing tests", encoding="utf-8")
    database = Database(tmp_path / "app.db")
    database.initialize()
    assert database.session_factory is not None
    vault_repository = VaultRepository(database.session_factory)
    vault_id = vault_repository.save_scan(vault, (), scan_vault(vault))
    document_ids = vault_repository.document_ids_for_paths(
        vault_id, ["First.md", "Second.md"]
    )
    repository = ExtractionRepository(database.session_factory)
    first = _candidate("Inspect first", document_ids["First.md"], "Inspect existing files")
    second = _candidate("Review first", document_ids["Second.md"], "Review existing tests")
    for candidate in (first, second):
        run_id = repository.start_run(model="mock", prompt_version="test-v1")
        repository.complete_run(run_id, ExtractionResult(candidates=[candidate]))
    saved = {item.candidate.name: item for item in repository.list_candidates()}

    merged_data = merge_candidate_data(
        saved["Inspect first"].candidate, saved["Review first"].candidate
    )
    merged = repository.create_merged_candidate(
        saved["Inspect first"].id,
        saved["Review first"].id,
        merged_data,
    )

    assert merged.status is CandidateStatus.PENDING
    assert len(merged.candidate.source_references) == 2
    statuses = {item.id: item.status for item in repository.list_candidates()}
    assert statuses[saved["Inspect first"].id] is CandidateStatus.ON_HOLD
    assert statuses[saved["Review first"].id] is CandidateStatus.ON_HOLD
    with database.session_factory() as session:
        lineage = session.scalars(select(CandidateMergeSourceRecord)).all()
        sources = session.scalars(
            select(SourceReferenceRecord).where(
                SourceReferenceRecord.candidate_id == merged.id
            )
        ).all()
        assert {item.source_candidate_id for item in lineage} == {
            saved["Inspect first"].id,
            saved["Review first"].id,
        }
        assert len(sources) == 2
        assert session.scalars(select(SkillDNARecord)).all() == []

    incomplete = merge_candidate_data(first, merged.candidate).model_copy(
        update={"source_references": first.source_references}
    )
    with pytest.raises(ValueError, match="preserve all validated sources"):
        repository.create_merged_candidate(
            saved["Inspect first"].id,
            merged.id,
            incomplete,
        )

    with pytest.raises(ValueError, match="already been merged"):
        repository.create_merged_candidate(
            saved["Inspect first"].id,
            saved["Review first"].id,
            merged_data,
        )
