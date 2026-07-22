from skill_dna_compiler.domain import WorkflowStep
from skill_dna_compiler.extraction.mock_provider import (
    StaticMockExtractionProvider,
    build_demo_extraction_result,
)
from skill_dna_compiler.extraction.payloads import ExtractionPayload, PayloadDocument
from skill_dna_compiler.extraction.schemas import (
    ExtractedCandidate,
    ExtractedSourceReference,
    ExtractionResult,
)


def test_mock_provider_returns_validated_copy_and_records_payload():
    payload = ExtractionPayload(
        documents=[
            PayloadDocument(
                document_id="doc_1",
                title="Note",
                path="Note.md",
                content_hash="a" * 64,
                content="Reusable rule",
            )
        ],
        redaction_count=0,
    )
    result = ExtractionResult(
        candidates=[
            ExtractedCandidate(
                name="Existing files first",
                description="Inspect existing files before creating new ones.",
                category="development",
                generality="cross-project",
                triggers=["Starting implementation"],
                do_not_use_when=[],
                principles=["Prefer reuse"],
                workflow=[WorkflowStep(order=1, action="Inspect files")],
                constraints=["Do not overwrite unrelated work"],
                source_references=[
                    ExtractedSourceReference(
                        document_id="doc_1",
                        quote="Reusable rule",
                        reason="Direct evidence",
                    )
                ],
                confidence=0.9,
                confidence_reason="Direct instruction",
                warnings=[],
            )
        ]
    )
    provider = StaticMockExtractionProvider(result)

    returned = provider.extract(payload)

    assert provider.last_payload == payload
    assert returned == result
    assert returned is not result


def test_build_demo_result_uses_an_exact_payload_quote():
    payload = ExtractionPayload(
        documents=[
            PayloadDocument(
                document_id="doc_1",
                title="Development rule",
                path="Rule.md",
                content_hash="a" * 64,
                content="\nReuse existing files before creating new ones.\n",
            )
        ],
        redaction_count=0,
    )

    result = build_demo_extraction_result(payload)

    assert len(result.candidates) == 1
    reference = result.candidates[0].source_references[0]
    assert reference.document_id == "doc_1"
    assert reference.quote in payload.documents[0].content
    assert "AIが抽出" in result.candidates[0].warnings[0]


def test_build_demo_result_allows_empty_documents():
    payload = ExtractionPayload(
        documents=[
            PayloadDocument(
                document_id="doc_1",
                title="Empty",
                path="Empty.md",
                content_hash="a" * 64,
                content="\n\n",
            )
        ],
        redaction_count=0,
    )

    assert build_demo_extraction_result(payload).candidates == []
