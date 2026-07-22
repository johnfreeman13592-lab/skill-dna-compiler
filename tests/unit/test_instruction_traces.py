from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from skill_dna_compiler.domain import InstructionTrace, TraceReviewStatus
from skill_dna_compiler.extraction.schemas import ExtractedCandidate
from skill_dna_compiler.review import (
    enumerate_traceable_instructions,
    reconcile_instruction_traces,
    require_valid_instruction_traces,
    source_reference_fingerprint,
    trace_gate_errors,
)


def _candidate() -> ExtractedCandidate:
    return ExtractedCandidate.model_validate(
        {
            "name": "Safe changes",
            "description": "Change existing code safely.",
            "category": "development",
            "generality": "cross-project",
            "triggers": ["Changing code"],
            "do_not_use_when": ["Read-only questions"],
            "principles": ["Inspect first"],
            "workflow": [{"order": 1, "action": "Review the implementation"}],
            "constraints": ["Run tests"],
            "source_references": [
                {
                    "document_id": "doc_test",
                    "quote": "Inspect first and run tests.",
                    "reason": "Synthetic direct rule",
                }
            ],
            "confidence": 0.9,
            "confidence_reason": "Synthetic fixture",
            "warnings": [],
        }
    )


def _approved_traces(candidate: ExtractedCandidate) -> list[InstructionTrace]:
    fingerprint = source_reference_fingerprint(candidate.source_references[0])
    return [
        InstructionTrace(
            instruction_key=item.key,
            instruction_hash=item.instruction_hash,
            source_reference_fingerprints=[fingerprint],
            review_status=TraceReviewStatus.APPROVED,
            traceability=2,
            fidelity=2,
            high_impact=False,
            reviewed_at=datetime.now(UTC),
        )
        for item in enumerate_traceable_instructions(candidate)
    ]


def test_trace_covers_description_and_every_rendered_instruction_section():
    keys = [item.key for item in enumerate_traceable_instructions(_candidate())]

    assert keys == [
        "description:1",
        "trigger:1",
        "do_not_use_when:1",
        "principle:1",
        "workflow:1",
        "constraint:1",
    ]


def test_every_instruction_must_have_strict_human_approval():
    candidate = _candidate()
    traces = _approved_traces(candidate)
    require_valid_instruction_traces(candidate, traces)

    traces[-1] = traces[-1].model_copy(
        update={"review_status": TraceReviewStatus.PENDING, "reviewed_at": None}
    )
    errors = trace_gate_errors(candidate, traces)

    assert any("constraint:1" in error and "承認" in error for error in errors)
    with pytest.raises(ValueError, match="DNA Trace gate failed"):
        require_valid_instruction_traces(candidate, traces)


def test_approved_high_impact_instruction_requires_complete_boundary():
    candidate = _candidate()
    instruction = enumerate_traceable_instructions(candidate)[-1]
    fingerprint = source_reference_fingerprint(candidate.source_references[0])

    with pytest.raises(ValidationError, match="boundary=2"):
        InstructionTrace(
            instruction_key=instruction.key,
            instruction_hash=instruction.instruction_hash,
            source_reference_fingerprints=[fingerprint],
            review_status=TraceReviewStatus.APPROVED,
            traceability=2,
            fidelity=2,
            high_impact=True,
            boundary=1,
            reviewed_at=datetime.now(UTC),
        )


def test_approved_instruction_requires_explicit_impact_decision():
    candidate = _candidate()
    instruction = enumerate_traceable_instructions(candidate)[0]
    fingerprint = source_reference_fingerprint(candidate.source_references[0])

    with pytest.raises(ValidationError, match="impact decision"):
        InstructionTrace(
            instruction_key=instruction.key,
            instruction_hash=instruction.instruction_hash,
            source_reference_fingerprints=[fingerprint],
            review_status=TraceReviewStatus.APPROVED,
            traceability=2,
            fidelity=2,
            reviewed_at=datetime.now(UTC),
        )


def test_edit_and_reorder_invalidate_only_current_instruction_occurrences():
    candidate = _candidate()
    traces = _approved_traces(candidate)
    edited_data = candidate.model_dump(mode="json")
    edited_data["description"] = "Review and change existing code safely."
    edited_data["workflow"] = [
        {"order": 1, "action": "Run focused tests"},
        {"order": 2, "action": "Review the implementation"},
    ]
    edited = ExtractedCandidate.model_validate(edited_data)

    reconciled = reconcile_instruction_traces(edited, traces)
    by_key = {trace.instruction_key: trace for trace in reconciled}

    assert by_key["description:1"].review_status is TraceReviewStatus.PENDING
    assert by_key["workflow:1"].review_status is TraceReviewStatus.PENDING
    assert by_key["workflow:2"].review_status is TraceReviewStatus.PENDING
    assert by_key["principle:1"].review_status is TraceReviewStatus.APPROVED


def test_unknown_source_fingerprint_fails_closed():
    candidate = _candidate()
    traces = _approved_traces(candidate)
    traces[0] = traces[0].model_copy(
        update={"source_reference_fingerprints": ["0" * 64]}
    )

    assert any("根拠参照" in error for error in trace_gate_errors(candidate, traces))
