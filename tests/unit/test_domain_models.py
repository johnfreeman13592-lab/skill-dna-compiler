from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from skill_dna_compiler.domain import Document, SkillCandidate, SourceReference


def test_document_rejects_path_traversal():
    with pytest.raises(ValidationError):
        Document(
            vault_id="vault_1",
            relative_path="../outside.md",
            title="Unsafe",
            content_hash="abc",
            modified_at=datetime.now(UTC),
        )


def test_candidate_requires_bounded_confidence():
    source = SourceReference(document_id="doc_1", quote="A reusable rule", reason="Evidence")

    with pytest.raises(ValidationError):
        SkillCandidate(
            name="Candidate",
            description="Description",
            category="development",
            source_references=[source],
            confidence=1.1,
            confidence_reason="Too high",
        )

