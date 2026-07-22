import pytest

from skill_dna_compiler.domain import WorkflowStep
from skill_dna_compiler.extraction.payloads import ExtractionPayload, PayloadDocument
from skill_dna_compiler.extraction.schemas import (
    ExtractedCandidate,
    ExtractedSourceReference,
    ExtractionResult,
)
from skill_dna_compiler.extraction.validator import (
    ExtractionValidationError,
    validate_source_quotes,
)


def _payload() -> ExtractionPayload:
    return ExtractionPayload(
        documents=[
            PayloadDocument(
                document_id="doc_1",
                title="Note",
                path="Note.md",
                content_hash="a" * 64,
                content="Inspect existing files before creating new ones.",
            )
        ],
        redaction_count=0,
    )


def _result(*, document_id: str = "doc_1", quote: str = "Inspect existing files"):
    return ExtractionResult(
        candidates=[
            ExtractedCandidate(
                name="Inspect first",
                description="Reuse what exists.",
                category="development",
                generality="cross-project",
                triggers=["Starting work"],
                do_not_use_when=[],
                principles=["Prefer reuse"],
                workflow=[WorkflowStep(order=1, action="Inspect files")],
                constraints=[],
                source_references=[
                    ExtractedSourceReference(
                        document_id=document_id,
                        quote=quote,
                        reason="Direct rule",
                    )
                ],
                confidence=0.9,
                confidence_reason="Direct statement",
                warnings=[],
            )
        ]
    )


def test_validate_source_quotes_accepts_exact_substring():
    result = _result()

    assert validate_source_quotes(result, _payload()) is result


@pytest.mark.parametrize(
    ("document_id", "quote", "message"),
    [
        ("unknown", "Inspect existing files", "unknown document"),
        ("doc_1", "inspect existing files", "not an exact source quote"),
    ],
)
def test_validate_source_quotes_rejects_unverifiable_sources(document_id, quote, message):
    with pytest.raises(ExtractionValidationError, match=message):
        validate_source_quotes(_result(document_id=document_id, quote=quote), _payload())


def test_validate_source_quotes_accepts_empty_result():
    result = ExtractionResult(candidates=[])

    assert validate_source_quotes(result, _payload()) is result
