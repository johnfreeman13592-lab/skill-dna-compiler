from __future__ import annotations

from skill_dna_compiler.extraction.payloads import ExtractionPayload
from skill_dna_compiler.extraction.schemas import ExtractionResult


class ExtractionValidationError(ValueError):
    """Raised when structured output is valid JSON but unsupported by its sources."""


def validate_source_quotes(
    result: ExtractionResult, payload: ExtractionPayload
) -> ExtractionResult:
    """Require every claimed quote to occur verbatim in its prepared document."""

    documents = {document.document_id: document.content for document in payload.documents}
    if len(documents) != len(payload.documents):
        raise ExtractionValidationError("Prepared documents contain duplicate identifiers")

    for candidate_index, candidate in enumerate(result.candidates, start=1):
        for reference_index, reference in enumerate(candidate.source_references, start=1):
            content = documents.get(reference.document_id)
            if content is None:
                raise ExtractionValidationError(
                    f"Candidate {candidate_index}, source {reference_index} refers to an "
                    "unknown document"
                )
            if reference.quote not in content:
                raise ExtractionValidationError(
                    f"Candidate {candidate_index}, source {reference_index} is not an exact "
                    "source quote"
                )
    return result
