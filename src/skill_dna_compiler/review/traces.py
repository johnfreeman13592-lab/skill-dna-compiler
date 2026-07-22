from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from skill_dna_compiler.domain import InstructionTrace, TraceReviewStatus

TRACE_POLICY_VERSION = "1.0"


@dataclass(frozen=True)
class TraceableInstruction:
    key: str
    text: str
    instruction_hash: str


def instruction_hash(key: str, text: str) -> str:
    payload = f"dna-trace:{TRACE_POLICY_VERSION}\0{key}\0{text}".encode()
    return hashlib.sha256(payload).hexdigest()


def source_reference_fingerprint(source: Any) -> str:
    payload = "\0".join((source.document_id, source.quote, source.reason)).encode()
    return hashlib.sha256(payload).hexdigest()


def enumerate_traceable_instructions(subject: Any) -> list[TraceableInstruction]:
    values: list[tuple[str, str]] = [("description:1", subject.description)]
    sections = (
        ("trigger", subject.triggers),
        ("do_not_use_when", subject.do_not_use_when),
        ("principle", subject.principles),
        ("workflow", [step.action for step in subject.workflow]),
        ("constraint", subject.constraints),
    )
    for section, items in sections:
        values.extend((f"{section}:{index}", text) for index, text in enumerate(items, 1))
    return [
        TraceableInstruction(key, text, instruction_hash(key, text))
        for key, text in values
    ]


def reconcile_instruction_traces(
    subject: Any, existing: Sequence[InstructionTrace]
) -> list[InstructionTrace]:
    current_sources = {
        source_reference_fingerprint(source) for source in _sources_for(subject)
    }
    existing_by_key: dict[str, InstructionTrace] = {}
    duplicate_keys: set[str] = set()
    for trace in existing:
        if trace.instruction_key in existing_by_key:
            duplicate_keys.add(trace.instruction_key)
        else:
            existing_by_key[trace.instruction_key] = trace
    reconciled: list[InstructionTrace] = []
    for instruction in enumerate_traceable_instructions(subject):
        previous = existing_by_key.get(instruction.key)
        if (
            instruction.key not in duplicate_keys
            and previous is not None
            and previous.instruction_hash == instruction.instruction_hash
            and set(previous.source_reference_fingerprints) <= current_sources
        ):
            reconciled.append(previous)
        else:
            reconciled.append(
                InstructionTrace(
                    instruction_key=instruction.key,
                    instruction_hash=instruction.instruction_hash,
                )
            )
    return reconciled


def trace_gate_errors(
    subject: Any, traces: Sequence[InstructionTrace] | None = None
) -> list[str]:
    traces = list(subject.instruction_traces if traces is None else traces)
    expected = enumerate_traceable_instructions(subject)
    expected_by_key = {item.key: item for item in expected}
    keys = [trace.instruction_key for trace in traces]
    errors: list[str] = []
    if (
        hasattr(subject, "trace_policy_version")
        and subject.trace_policy_version != TRACE_POLICY_VERSION
    ):
        errors.append("このSkill DNAは現行DNA Trace policyで確認されていません。")
    if len(keys) != len(set(keys)):
        errors.append("Traceに重複した指示キーがあります。")
    missing = [item.key for item in expected if item.key not in keys]
    orphaned = [key for key in keys if key not in expected_by_key]
    if missing:
        errors.append("未確認の指示があります: " + ", ".join(missing))
    if orphaned:
        errors.append("現在のSkillに存在しないTraceがあります: " + ", ".join(orphaned))
    current_sources = {
        source_reference_fingerprint(source) for source in _sources_for(subject)
    }
    for trace in traces:
        instruction = expected_by_key.get(trace.instruction_key)
        if instruction is None:
            continue
        if trace.instruction_hash != instruction.instruction_hash:
            errors.append(f"{trace.instruction_key} は編集後に再確認されていません。")
        if set(trace.source_reference_fingerprints) - current_sources:
            errors.append(f"{trace.instruction_key} の根拠参照が一致しません。")
        if trace.review_status is not TraceReviewStatus.APPROVED:
            errors.append(f"{trace.instruction_key} は人が承認していません。")
        elif not trace.source_reference_fingerprints:
            errors.append(f"{trace.instruction_key} に直接根拠がありません。")
        elif trace.traceability != 2 or trace.fidelity != 2:
            errors.append(f"{trace.instruction_key} は直接根拠・意味一致を満たしません。")
        elif trace.high_impact is None:
            errors.append(f"{trace.instruction_key} は影響度を人が確認していません。")
        elif trace.high_impact and trace.boundary != 2:
            errors.append(f"{trace.instruction_key} は安全境界の確認が不足しています。")
        elif trace.reviewed_at is None:
            errors.append(f"{trace.instruction_key} に人の確認日時がありません。")
    return errors


def require_valid_instruction_traces(
    subject: Any, traces: Sequence[InstructionTrace] | None = None
) -> None:
    errors = trace_gate_errors(subject, traces)
    if errors:
        raise ValueError("DNA Trace gate failed: " + " ".join(errors))


def _sources_for(subject: Any) -> Sequence[Any]:
    return subject.source_references if hasattr(subject, "source_references") else subject.sources
