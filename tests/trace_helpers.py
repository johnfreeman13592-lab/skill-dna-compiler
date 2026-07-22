from datetime import UTC, datetime

from skill_dna_compiler.domain import InstructionTrace, TraceReviewStatus
from skill_dna_compiler.review import (
    reconcile_instruction_traces,
    source_reference_fingerprint,
)


def approve_all_candidate_traces(repository, saved):
    """Simulate explicit human approval for synthetic test candidates only."""

    current = saved
    fingerprints = [
        source_reference_fingerprint(source)
        for source in current.candidate.source_references
    ]
    for pending in reconcile_instruction_traces(
        current.candidate, current.instruction_traces
    ):
        approved = InstructionTrace(
            instruction_key=pending.instruction_key,
            instruction_hash=pending.instruction_hash,
            source_reference_fingerprints=fingerprints,
            review_status=TraceReviewStatus.APPROVED,
            traceability=2,
            fidelity=2,
            high_impact=False,
            reviewed_at=datetime.now(UTC),
        )
        current = repository.save_instruction_trace(current.id, approved)
    return current
