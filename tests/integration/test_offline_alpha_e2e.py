import re
from pathlib import Path

import pytest

from skill_dna_compiler.domain import CandidateStatus
from skill_dna_compiler.exporting import SkillExportService
from skill_dna_compiler.extraction import prepare_extraction_payload
from skill_dna_compiler.extraction.mock_provider import StaticMockExtractionProvider
from skill_dna_compiler.extraction.schemas import ExtractionResult
from skill_dna_compiler.extraction.service import ExtractionService
from skill_dna_compiler.skill_dna import SkillDNAService
from skill_dna_compiler.storage.database import Database, SkillCandidateRecord
from skill_dna_compiler.storage.repositories import (
    ExportRepository,
    ExtractionRepository,
    SkillDNARepository,
    VaultRepository,
)
from skill_dna_compiler.vault import parse_markdown_file, scan_vault
from tests.trace_helpers import approve_all_candidate_traces

FIXTURES = Path(__file__).parents[1] / "fixtures"
SAMPLE_VAULT = FIXTURES / "sample_vault"
EXPECTED_SKILL = FIXTURES / "expected" / "safe-code-change" / "SKILL.md"
SYNTHETIC_SECRET = "SYNTHETIC_SAMPLE_VALUE_123"


def test_offline_sample_vault_to_exported_skill(tmp_path):
    original_vault = {
        path.relative_to(SAMPLE_VAULT): path.read_bytes()
        for path in SAMPLE_VAULT.rglob("*")
        if path.is_file()
    }
    database = Database(tmp_path / "offline-e2e.sqlite3")
    database.initialize()
    sessions = database.session_factory
    assert sessions is not None

    vault_files = scan_vault(SAMPLE_VAULT)
    assert [item.relative_path for item in vault_files] == [
        "01-inspect-first.md",
        "02-verify-changes.md",
    ]
    vaults = VaultRepository(sessions)
    vault_id = vaults.save_scan(SAMPLE_VAULT, (), vault_files)
    document_ids = vaults.document_ids_for_paths(
        vault_id, [item.relative_path for item in vault_files]
    )
    notes = [parse_markdown_file(item) for item in vault_files]
    prepared = prepare_extraction_payload(
        notes,
        max_characters=50_000,
        document_ids_by_path=document_ids,
    )

    assert SYNTHETIC_SECRET not in prepared.serialized_json
    assert prepared.payload.redaction_count == 1
    assert [document.path for document in prepared.payload.documents] == [
        "01-inspect-first.md",
        "02-verify-changes.md",
    ]

    result = ExtractionResult.model_validate(
        {
            "candidates": [
                {
                    "name": "Safe Code Change",
                    "description": (
                        "Inspect existing project context before editing and verify "
                        "changes in increasing scope."
                    ),
                    "category": "development",
                    "generality": "cross-project",
                    "triggers": ["Changing code in an existing project"],
                    "do_not_use_when": ["Only answering a read-only question"],
                    "principles": [
                        "Inspect before editing",
                        "Reuse existing implementation before adding files",
                    ],
                    "workflow": [
                        {
                            "order": 1,
                            "action": (
                                "Inspect the README, architecture, and current "
                                "implementation"
                            ),
                        },
                        {"order": 2, "action": "Make the smallest relevant change"},
                        {
                            "order": 3,
                            "action": (
                                "Run focused checks, then the full test suite and lint"
                            ),
                        },
                    ],
                    "constraints": [
                        "Run focused tests before full verification",
                        "Do not report completion while required checks fail",
                    ],
                    "source_references": [
                        {
                            "document_id": document_ids["01-inspect-first.md"],
                            "quote": (
                                "Before changing code, inspect the README, architecture, "
                                "and existing implementation."
                            ),
                            "reason": (
                                "Direct instruction to inspect existing project context"
                            ),
                        },
                        {
                            "document_id": document_ids["02-verify-changes.md"],
                            "quote": (
                                "Then run the full test suite and lint before reporting "
                                "completion."
                            ),
                            "reason": (
                                "Direct instruction to verify changes before completion"
                            ),
                        },
                    ],
                    "confidence": 1.0,
                    "confidence_reason": "Deterministic offline E2E fixture",
                    "warnings": ["Synthetic fixture; not an AI-generated candidate"],
                }
            ]
        }
    )
    candidates = ExtractionRepository(sessions)
    provider = StaticMockExtractionProvider(result)
    extracted = ExtractionService(candidates).run(
        payload=prepared.payload,
        provider=provider,
        model="offline-static-fixture",
        prompt_version="offline-e2e-v1",
    )

    assert extracted == result
    assert provider.last_payload == prepared.payload
    saved = candidates.list_candidates()
    assert len(saved) == 1
    assert saved[0].status is CandidateStatus.PENDING

    # Simulate a beta.2-era approved row: the old app could approve a candidate
    # without instruction-level DNA Trace metadata. A restart must preserve the
    # row for re-review while keeping downstream conversion fail-closed.
    with sessions() as session:
        legacy_record = session.get(SkillCandidateRecord, saved[0].id)
        assert legacy_record is not None
        legacy_record.status = CandidateStatus.APPROVED.value
        session.commit()
    assert database.engine is not None
    database.engine.dispose()

    restarted_database = Database(database.path)
    restarted_database.initialize()
    restarted_sessions = restarted_database.session_factory
    assert restarted_sessions is not None
    candidates = ExtractionRepository(restarted_sessions)
    legacy_saved = candidates.get_candidate(saved[0].id)
    assert legacy_saved.status is CandidateStatus.APPROVED
    assert legacy_saved.instruction_traces == ()
    with pytest.raises(ValueError, match="DNA Trace"):
        SkillDNAService(
            candidates, SkillDNARepository(restarted_sessions)
        ).convert_approved_candidate(legacy_saved.id)

    candidates.set_candidate_status(legacy_saved.id, CandidateStatus.PENDING)
    approve_all_candidate_traces(candidates, legacy_saved)
    candidates.set_candidate_status(saved[0].id, CandidateStatus.APPROVED)

    skills = SkillDNARepository(restarted_sessions)
    skill = SkillDNAService(candidates, skills).convert_approved_candidate(saved[0].id)
    assert skill.version == "0.1.0"
    assert [version.version for version in skills.list_versions(skill.id)] == ["0.1.0"]

    destination = tmp_path / "exports"
    destination.mkdir()
    exports = ExportRepository(restarted_sessions)
    export_service = SkillExportService(exports)
    plan = export_service.prepare(skill, destination)
    exported = export_service.export(plan)

    assert exported == destination / "safe-code-change" / "SKILL.md"
    assert exported.read_text(encoding="utf-8") == plan.content
    normalized = re.sub(r"`doc_[0-9a-f]+`", "`<DOCUMENT_ID>`", plan.content)
    assert normalized == EXPECTED_SKILL.read_text(encoding="utf-8")
    assert [item.exported_version for item in exports.list_for_skill(skill.id)] == [
        "0.1.0"
    ]

    # Reopen the same SQLite file once more to prove that the approved traces,
    # immutable Skill snapshot, and export history survive a real app restart.
    assert restarted_database.engine is not None
    restarted_database.engine.dispose()
    final_database = Database(restarted_database.path)
    final_database.initialize()
    final_sessions = final_database.session_factory
    assert final_sessions is not None
    final_candidates = ExtractionRepository(final_sessions)
    final_candidate = final_candidates.get_candidate(saved[0].id)
    assert final_candidate.status is CandidateStatus.APPROVED
    assert final_candidate.instruction_traces
    final_skills = SkillDNARepository(final_sessions)
    final_skill = final_skills.get_by_candidate(saved[0].id)
    assert final_skill == skill
    final_exports = ExportRepository(final_sessions)
    final_exports.assert_exportable(final_skill)
    assert [
        item.exported_version for item in final_exports.list_for_skill(final_skill.id)
    ] == ["0.1.0"]
    assert original_vault == {
        path.relative_to(SAMPLE_VAULT): path.read_bytes()
        for path in SAMPLE_VAULT.rglob("*")
        if path.is_file()
    }
