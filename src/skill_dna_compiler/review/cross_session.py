from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProposalDecision(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    NO_SKILL = "no_skill"


class NoSkillDestination(StrEnum):
    AGENTS = "agents"
    MEMORY = "memory"
    MCP = "mcp"
    WORKFLOW = "workflow"
    NONE = "none"


class EvidenceDimension(StrEnum):
    TRIGGER = "trigger"
    DO_NOT_USE = "do_not_use"
    DECISION = "decision"
    PROCEDURE = "procedure"
    SAFETY = "safety"
    EVALUATION = "evaluation"


class EvidenceStatus(StrEnum):
    SUPPORTED = "supported"
    INFERRED = "inferred"
    UNKNOWN = "unknown"
    NEEDS_CONFIRMATION = "needs_confirmation"


class TrialLabel(StrEnum):
    A = "A"
    B = "B"


_SAFE_ID_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"
MIN_SUPPORTED_EVIDENCE_IDS = 1
MAX_SUPPORTED_EVIDENCE_IDS = 20
MIN_SELECTED_EVIDENCE_IDS_PER_TRIAL = 1
MAX_SELECTED_EVIDENCE_IDS_PER_TRIAL = 40
MIN_PROPOSALS_PER_TRIAL = 1
MAX_PROPOSALS_PER_TRIAL = 20


class DimensionEvidence(BaseModel):
    """Body-free evidence state backed only by selected opaque identifiers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: EvidenceDimension
    status: EvidenceStatus
    evidence_ids: tuple[str, ...] = ()

    @field_validator("evidence_ids")
    @classmethod
    def evidence_ids_must_be_safe_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted(value))
        if len(normalized) > MAX_SUPPORTED_EVIDENCE_IDS:
            raise ValueError(
                f"supported evidence accepts at most {MAX_SUPPORTED_EVIDENCE_IDS} evidence_ids"
            )
        if len(normalized) != len(set(normalized)):
            raise ValueError("evidence_ids must be unique")
        for evidence_id in normalized:
            _validate_safe_id(evidence_id, field_name="evidence_id")
        return normalized

    @model_validator(mode="after")
    def status_must_match_evidence(self) -> DimensionEvidence:
        if (
            self.status is EvidenceStatus.SUPPORTED
            and len(self.evidence_ids) < MIN_SUPPORTED_EVIDENCE_IDS
        ):
            raise ValueError(
                "supported evidence requires at least "
                f"{MIN_SUPPORTED_EVIDENCE_IDS} evidence_id"
            )
        if self.status is not EvidenceStatus.SUPPORTED and self.evidence_ids:
            raise ValueError("only supported evidence can carry evidence_ids")
        return self


class TrialProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str = Field(pattern=_SAFE_ID_PATTERN)
    decision: ProposalDecision
    existing_skill_id: str | None = Field(default=None, pattern=_SAFE_ID_PATTERN)
    no_skill_destination: NoSkillDestination | None = None
    evidence: tuple[DimensionEvidence, ...]

    @model_validator(mode="after")
    def decision_fields_and_dimensions_must_be_complete(self) -> TrialProposal:
        if self.decision is ProposalDecision.UPDATE:
            if self.existing_skill_id is None:
                raise ValueError("update requires existing_skill_id")
            if self.no_skill_destination is not None:
                raise ValueError("update cannot have no_skill_destination")
        elif self.decision is ProposalDecision.NO_SKILL:
            if self.no_skill_destination is None:
                raise ValueError("no_skill requires no_skill_destination")
            if self.existing_skill_id is not None:
                raise ValueError("no_skill cannot have existing_skill_id")
        elif self.existing_skill_id is not None or self.no_skill_destination is not None:
            raise ValueError("create cannot have update or no_skill fields")

        dimensions = [item.dimension for item in self.evidence]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("each evidence dimension must appear exactly once")
        if set(dimensions) != set(EvidenceDimension):
            raise ValueError("all evidence dimensions must be supplied explicitly")
        return self


class TrialResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: TrialLabel
    selected_evidence_ids: tuple[str, ...]
    proposals: tuple[TrialProposal, ...]

    @field_validator("selected_evidence_ids")
    @classmethod
    def selected_ids_must_be_safe_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted(value))
        if len(normalized) < MIN_SELECTED_EVIDENCE_IDS_PER_TRIAL:
            raise ValueError(
                "a trial requires at least "
                f"{MIN_SELECTED_EVIDENCE_IDS_PER_TRIAL} selected_evidence_id"
            )
        if len(normalized) > MAX_SELECTED_EVIDENCE_IDS_PER_TRIAL:
            raise ValueError(
                "a trial accepts at most "
                f"{MAX_SELECTED_EVIDENCE_IDS_PER_TRIAL} selected_evidence_ids"
            )
        if len(normalized) != len(set(normalized)):
            raise ValueError("selected_evidence_ids must be unique")
        for evidence_id in normalized:
            _validate_safe_id(evidence_id, field_name="selected_evidence_id")
        return normalized

    @model_validator(mode="after")
    def proposals_must_be_unique_and_selected(self) -> TrialResult:
        if len(self.proposals) < MIN_PROPOSALS_PER_TRIAL:
            raise ValueError(
                f"a trial requires at least {MIN_PROPOSALS_PER_TRIAL} proposal"
            )
        if len(self.proposals) > MAX_PROPOSALS_PER_TRIAL:
            raise ValueError(
                f"a trial accepts at most {MAX_PROPOSALS_PER_TRIAL} proposals"
            )
        proposal_ids = [proposal.proposal_id for proposal in self.proposals]
        if len(proposal_ids) != len(set(proposal_ids)):
            raise ValueError("proposal_id values must be unique within a trial")

        selected = set(self.selected_evidence_ids)
        for proposal in self.proposals:
            used = {
                evidence_id
                for dimension in proposal.evidence
                for evidence_id in dimension.evidence_ids
            }
            if not used <= selected:
                raise ValueError("proposal evidence must be explicitly selected for its trial")
        return self


class CrossSessionComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trial_a: TrialResult
    trial_b: TrialResult

    @model_validator(mode="after")
    def trials_must_form_a_comparable_pair(self) -> CrossSessionComparison:
        if self.trial_a.label is not TrialLabel.A or self.trial_b.label is not TrialLabel.B:
            raise ValueError("trial_a and trial_b must use labels A and B")
        if not set(self.trial_a.selected_evidence_ids) <= set(
            self.trial_b.selected_evidence_ids
        ):
            raise ValueError("Trial B must retain every evidence selection from Trial A")
        if {item.proposal_id for item in self.trial_a.proposals} != {
            item.proposal_id for item in self.trial_b.proposals
        }:
            raise ValueError("Trial A and Trial B must contain the same proposal_id values")
        trial_a = {item.proposal_id: item for item in self.trial_a.proposals}
        for right in self.trial_b.proposals:
            left = trial_a[right.proposal_id]
            if (
                left.decision is ProposalDecision.UPDATE
                and right.decision is ProposalDecision.UPDATE
                and left.existing_skill_id != right.existing_skill_id
            ):
                raise ValueError(
                    "paired update proposals must target the same existing_skill_id"
                )
        return self


def render_cross_session_markdown(comparison: CrossSessionComparison) -> str:
    """Render a deterministic, body-free local comparison report."""

    trial_a = {item.proposal_id: item for item in comparison.trial_a.proposals}
    trial_b = {item.proposal_id: item for item in comparison.trial_b.proposals}
    lines = [
        "# Cross-Session Skill Discovery A/B comparison",
        "",
        "- Scope: local comparison of explicitly selected opaque evidence IDs",
        "- Raw note bodies, source quotes, credentials, and unselected records: not accepted",
        f"- Trial A selected evidence: {len(comparison.trial_a.selected_evidence_ids)}",
        f"- Trial B selected evidence: {len(comparison.trial_b.selected_evidence_ids)}",
    ]

    for number, proposal_id in enumerate(sorted(trial_a), start=1):
        left = trial_a[proposal_id]
        right = trial_b[proposal_id]
        lines.extend(
            [
                "",
                f"## Proposal {number}",
                "",
                "| Field | Trial A | Trial B |",
                "|---|---|---|",
                f"| Decision | `{left.decision.value}` | `{right.decision.value}` |",
                (
                    "| Existing Skill | "
                    f"{_display_presence(left.existing_skill_id)} | "
                    f"{_display_presence(right.existing_skill_id)} |"
                ),
                (
                    "| No-Skill destination | "
                    f"{_display_destination(left.no_skill_destination)} | "
                    f"{_display_destination(right.no_skill_destination)} |"
                ),
                "",
                "| DNA evidence | Trial A | Trial B | B change |",
                "|---|---|---|---|",
            ]
        )
        left_dimensions = {item.dimension: item for item in left.evidence}
        right_dimensions = {item.dimension: item for item in right.evidence}
        for dimension in EvidenceDimension:
            left_evidence = left_dimensions[dimension]
            right_evidence = right_dimensions[dimension]
            lines.append(
                f"| `{dimension.value}` | {_display_evidence(left_evidence)} | "
                f"{_display_evidence(right_evidence)} | "
                f"{_describe_change(left_evidence, right_evidence)} |"
            )
    return "\n".join(lines) + "\n"


def _validate_safe_id(value: str, *, field_name: str) -> None:
    if re.fullmatch(_SAFE_ID_PATTERN, value) is None:
        raise ValueError(f"{field_name} must be an opaque lowercase identifier")


def _display_presence(value: str | None) -> str:
    return "`provided`" if value is not None else "—"


def _display_destination(value: NoSkillDestination | None) -> str:
    return f"`{value.value}`" if value is not None else "—"


def _display_evidence(value: DimensionEvidence) -> str:
    if value.status is EvidenceStatus.SUPPORTED:
        return f"`supported` ({len(value.evidence_ids)} selected source(s))"
    return f"`{value.status.value}`"


def _describe_change(left: DimensionEvidence, right: DimensionEvidence) -> str:
    if right.status is not EvidenceStatus.SUPPORTED:
        return f"`{right.status.value}`"
    if left.status is not EvidenceStatus.SUPPORTED:
        return "`newly_supported`"
    added = sorted(set(right.evidence_ids) - set(left.evidence_ids))
    removed = sorted(set(left.evidence_ids) - set(right.evidence_ids))
    if not added and not removed:
        return "`unchanged`"
    parts = []
    if added:
        parts.append(f"added {len(added)} selected source(s)")
    if removed:
        parts.append(f"removed {len(removed)} selected source(s)")
    return "; ".join(parts)
