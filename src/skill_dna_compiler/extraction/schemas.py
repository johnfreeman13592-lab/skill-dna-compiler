from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from skill_dna_compiler.domain import WorkflowStep


class ExtractedSourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    quote: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ExtractedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1)
    category: str = Field(min_length=1)
    generality: str
    triggers: list[str]
    do_not_use_when: list[str]
    principles: list[str]
    workflow: list[WorkflowStep]
    constraints: list[str]
    source_references: list[ExtractedSourceReference] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    confidence_reason: str = Field(min_length=1)
    warnings: list[str]


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[ExtractedCandidate]
