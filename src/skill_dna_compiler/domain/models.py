from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class CandidateStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ON_HOLD = "on_hold"


class TraceReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SkillUsageStatus(StrEnum):
    NOT_USED = "not_used"
    USED_ONCE = "used_once"
    REUSED = "reused"


class SkillUsefulness(StrEnum):
    NOT_EVALUATED = "not_evaluated"
    HELPFUL = "helpful"
    PARTLY_HELPFUL = "partly_helpful"
    NOT_HELPFUL = "not_helpful"


class Document(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: _new_id("doc"))
    vault_id: str
    relative_path: str
    title: str
    content_hash: str
    modified_at: datetime
    indexed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("relative_path")
    @classmethod
    def relative_path_must_be_safe(cls, value: str) -> str:
        path = PurePosixPath(value.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("relative_path must stay inside its Vault")
        return path.as_posix()


class SourceReference(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("source"))
    document_id: str
    quote: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    heading: str | None = None
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)


class WorkflowStep(BaseModel):
    order: int = Field(ge=1)
    action: str = Field(min_length=1)


class InstructionTrace(BaseModel):
    instruction_key: str = Field(
        pattern=r"^(description|trigger|do_not_use_when|principle|workflow|constraint):[1-9]\d*$"
    )
    instruction_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_reference_fingerprints: list[str] = Field(default_factory=list)
    review_status: TraceReviewStatus = TraceReviewStatus.PENDING
    traceability: int = Field(default=0, ge=0, le=2)
    fidelity: int = Field(default=0, ge=0, le=2)
    boundary: int | None = Field(default=None, ge=0, le=2)
    high_impact: bool | None = None
    reviewer_note: str = Field(default="", max_length=500)
    reviewed_at: datetime | None = None

    @field_validator("source_reference_fingerprints")
    @classmethod
    def source_fingerprints_must_be_unique_and_valid(cls, value: list[str]) -> list[str]:
        if any(
            len(item) != 64
            or any(character not in "0123456789abcdef" for character in item)
            for item in value
        ):
            raise ValueError("source reference fingerprints must be SHA-256 values")
        if len(value) != len(set(value)):
            raise ValueError("source reference fingerprints must be unique")
        return value

    @model_validator(mode="after")
    def approved_trace_must_satisfy_the_strict_gate(self) -> InstructionTrace:
        if self.review_status is not TraceReviewStatus.APPROVED:
            return self
        if not self.source_reference_fingerprints:
            raise ValueError("an approved trace requires at least one source reference")
        if self.traceability != 2 or self.fidelity != 2:
            raise ValueError("an approved trace requires traceability=2 and fidelity=2")
        if self.high_impact is None:
            raise ValueError("an approved trace requires an explicit impact decision")
        if self.high_impact and self.boundary != 2:
            raise ValueError("an approved high-impact trace requires boundary=2")
        if self.reviewed_at is None:
            raise ValueError("an approved trace requires reviewed_at")
        return self


class SkillCandidate(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("candidate"))
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1)
    category: str = Field(min_length=1)
    generality: str = "cross-project"
    triggers: list[str] = Field(default_factory=list)
    do_not_use_when: list[str] = Field(default_factory=list)
    principles: list[str] = Field(default_factory=list)
    workflow: list[WorkflowStep] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)
    instruction_traces: list[InstructionTrace] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    confidence_reason: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
    status: CandidateStatus = CandidateStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SkillDNA(BaseModel):
    schema_version: str = "1.0"
    trace_policy_version: str | None = None
    id: str = Field(default_factory=lambda: _new_id("skill"))
    candidate_id: str
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(min_length=1)
    status: CandidateStatus = CandidateStatus.APPROVED
    version: str = Field(default="0.1.0", pattern=r"^\d+\.\d+\.\d+$")
    triggers: list[str] = Field(default_factory=list)
    do_not_use_when: list[str] = Field(default_factory=list)
    principles: list[str] = Field(default_factory=list)
    workflow: list[WorkflowStep] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)
    instruction_traces: list[InstructionTrace] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
