import pytest
from pydantic import ValidationError

from skill_dna_compiler.review.cross_session import (
    MAX_PROPOSALS_PER_TRIAL,
    MAX_SELECTED_EVIDENCE_IDS_PER_TRIAL,
    MAX_SUPPORTED_EVIDENCE_IDS,
    MIN_PROPOSALS_PER_TRIAL,
    MIN_SELECTED_EVIDENCE_IDS_PER_TRIAL,
    MIN_SUPPORTED_EVIDENCE_IDS,
    CrossSessionComparison,
    DimensionEvidence,
    EvidenceDimension,
    EvidenceStatus,
    NoSkillDestination,
    ProposalDecision,
    TrialLabel,
    TrialProposal,
    TrialResult,
    render_cross_session_markdown,
)


def _evidence(
    *,
    supported: dict[EvidenceDimension, tuple[str, ...]] | None = None,
) -> tuple[DimensionEvidence, ...]:
    supported = supported or {}
    return tuple(
        DimensionEvidence(
            dimension=dimension,
            status=(
                EvidenceStatus.SUPPORTED
                if dimension in supported
                else EvidenceStatus.UNKNOWN
            ),
            evidence_ids=supported.get(dimension, ()),
        )
        for dimension in EvidenceDimension
    )


def _proposal(
    *,
    decision: ProposalDecision,
    proposal_id: str = "proposal_one",
    evidence: tuple[DimensionEvidence, ...] | None = None,
    existing_skill_id: str | None = None,
    no_skill_destination: NoSkillDestination | None = None,
) -> TrialProposal:
    return TrialProposal(
        proposal_id=proposal_id,
        decision=decision,
        existing_skill_id=existing_skill_id,
        no_skill_destination=no_skill_destination,
        evidence=evidence or _evidence(),
    )


def _trial(
    label: TrialLabel,
    proposal: TrialProposal,
    *,
    selected: tuple[str, ...],
) -> TrialResult:
    return TrialResult(label=label, selected_evidence_ids=selected, proposals=(proposal,))


@pytest.mark.parametrize(
    ("decision", "existing_skill_id", "destination"),
    [
        (ProposalDecision.CREATE, None, None),
        (ProposalDecision.UPDATE, "skill_one", None),
        (ProposalDecision.NO_SKILL, None, NoSkillDestination.AGENTS),
        (ProposalDecision.NO_SKILL, None, NoSkillDestination.MEMORY),
        (ProposalDecision.NO_SKILL, None, NoSkillDestination.MCP),
        (ProposalDecision.NO_SKILL, None, NoSkillDestination.WORKFLOW),
        (ProposalDecision.NO_SKILL, None, NoSkillDestination.NONE),
    ],
)
def test_classification_accepts_only_valid_decision_fields(
    decision,
    existing_skill_id,
    destination,
):
    proposal = _proposal(
        decision=decision,
        existing_skill_id=existing_skill_id,
        no_skill_destination=destination,
    )

    assert proposal.decision is decision
    assert proposal.existing_skill_id == existing_skill_id
    assert proposal.no_skill_destination is destination


@pytest.mark.parametrize(
    "values",
    [
        {"decision": ProposalDecision.UPDATE},
        {
            "decision": ProposalDecision.CREATE,
            "existing_skill_id": "skill_one",
        },
        {"decision": ProposalDecision.NO_SKILL},
        {
            "decision": ProposalDecision.NO_SKILL,
            "existing_skill_id": "skill_one",
            "no_skill_destination": NoSkillDestination.NONE,
        },
        {
            "decision": ProposalDecision.UPDATE,
            "existing_skill_id": "skill_one",
            "no_skill_destination": NoSkillDestination.MEMORY,
        },
    ],
)
def test_classification_fails_closed_for_invalid_combinations(values):
    with pytest.raises(ValidationError):
        _proposal(**values)


def test_evidence_requires_every_dimension_exactly_once():
    incomplete = _evidence()[:-1]
    duplicated = (*_evidence()[:-1], _evidence()[0])

    with pytest.raises(ValidationError, match="all evidence dimensions"):
        _proposal(decision=ProposalDecision.CREATE, evidence=incomplete)
    with pytest.raises(ValidationError, match="exactly once"):
        _proposal(decision=ProposalDecision.CREATE, evidence=duplicated)


@pytest.mark.parametrize(
    "status",
    [
        EvidenceStatus.INFERRED,
        EvidenceStatus.UNKNOWN,
        EvidenceStatus.NEEDS_CONFIRMATION,
    ],
)
def test_non_supported_states_cannot_smuggle_evidence_ids(status):
    with pytest.raises(ValidationError, match="only supported"):
        DimensionEvidence(
            dimension=EvidenceDimension.TRIGGER,
            status=status,
            evidence_ids=("evidence_one",),
        )


def test_supported_requires_direct_selected_evidence():
    with pytest.raises(ValidationError, match="supported evidence requires"):
        DimensionEvidence(
            dimension=EvidenceDimension.TRIGGER,
            status=EvidenceStatus.SUPPORTED,
        )


def test_supported_evidence_accepts_minimum_and_maximum_bounds():
    minimum = DimensionEvidence(
        dimension=EvidenceDimension.TRIGGER,
        status=EvidenceStatus.SUPPORTED,
        evidence_ids=tuple(
            f"evidence_{index}" for index in range(MIN_SUPPORTED_EVIDENCE_IDS)
        ),
    )
    maximum = DimensionEvidence(
        dimension=EvidenceDimension.TRIGGER,
        status=EvidenceStatus.SUPPORTED,
        evidence_ids=tuple(
            f"evidence_{index}" for index in range(MAX_SUPPORTED_EVIDENCE_IDS)
        ),
    )

    assert len(minimum.evidence_ids) == MIN_SUPPORTED_EVIDENCE_IDS
    assert len(maximum.evidence_ids) == MAX_SUPPORTED_EVIDENCE_IDS


def test_supported_evidence_rejects_over_limit():
    with pytest.raises(ValidationError, match="at most 20 evidence_ids"):
        DimensionEvidence(
            dimension=EvidenceDimension.TRIGGER,
            status=EvidenceStatus.SUPPORTED,
            evidence_ids=tuple(
                f"evidence_{index}"
                for index in range(MAX_SUPPORTED_EVIDENCE_IDS + 1)
            ),
        )


def test_trial_rejects_unselected_evidence():
    proposal = _proposal(
        decision=ProposalDecision.CREATE,
        evidence=_evidence(
            supported={EvidenceDimension.TRIGGER: ("evidence_not_selected",)}
        ),
    )

    with pytest.raises(ValidationError, match="explicitly selected"):
        _trial(TrialLabel.A, proposal, selected=("evidence_one",))


def test_trial_accepts_minimum_and_maximum_selected_evidence_bounds():
    proposal = _proposal(decision=ProposalDecision.CREATE)
    minimum = _trial(
        TrialLabel.A,
        proposal,
        selected=tuple(
            f"evidence_{index}"
            for index in range(MIN_SELECTED_EVIDENCE_IDS_PER_TRIAL)
        ),
    )
    maximum = _trial(
        TrialLabel.B,
        proposal,
        selected=tuple(
            f"evidence_{index}"
            for index in range(MAX_SELECTED_EVIDENCE_IDS_PER_TRIAL)
        ),
    )

    assert len(minimum.selected_evidence_ids) == MIN_SELECTED_EVIDENCE_IDS_PER_TRIAL
    assert len(maximum.selected_evidence_ids) == MAX_SELECTED_EVIDENCE_IDS_PER_TRIAL


def test_trial_rejects_empty_and_over_limit_selected_evidence():
    proposal = _proposal(decision=ProposalDecision.CREATE)

    with pytest.raises(ValidationError, match="requires at least 1 selected_evidence_id"):
        _trial(TrialLabel.A, proposal, selected=())
    with pytest.raises(ValidationError, match="at most 40 selected_evidence_ids"):
        _trial(
            TrialLabel.A,
            proposal,
            selected=tuple(
                f"evidence_{index}"
                for index in range(MAX_SELECTED_EVIDENCE_IDS_PER_TRIAL + 1)
            ),
        )


def test_comparison_accepts_minimum_and_maximum_proposal_bounds():
    selected = tuple(
        f"evidence_{index}"
        for index in range(MAX_SELECTED_EVIDENCE_IDS_PER_TRIAL)
    )
    minimum_proposals = tuple(
        _proposal(
            decision=ProposalDecision.CREATE,
            proposal_id=f"proposal_{index}",
        )
        for index in range(MIN_PROPOSALS_PER_TRIAL)
    )
    maximum_proposals = tuple(
        _proposal(
            decision=ProposalDecision.CREATE,
            proposal_id=f"proposal_{index}",
        )
        for index in range(MAX_PROPOSALS_PER_TRIAL)
    )

    minimum = CrossSessionComparison(
        trial_a=TrialResult(
            label=TrialLabel.A,
            selected_evidence_ids=(selected[0],),
            proposals=minimum_proposals,
        ),
        trial_b=TrialResult(
            label=TrialLabel.B,
            selected_evidence_ids=(selected[0],),
            proposals=minimum_proposals,
        ),
    )
    maximum = CrossSessionComparison(
        trial_a=TrialResult(
            label=TrialLabel.A,
            selected_evidence_ids=selected,
            proposals=maximum_proposals,
        ),
        trial_b=TrialResult(
            label=TrialLabel.B,
            selected_evidence_ids=selected,
            proposals=maximum_proposals,
        ),
    )

    assert len(minimum.trial_a.proposals) == MIN_PROPOSALS_PER_TRIAL
    assert len(maximum.trial_b.proposals) == MAX_PROPOSALS_PER_TRIAL


def test_trial_rejects_empty_comparison_and_over_limit_proposals():
    selected = ("evidence_one",)

    with pytest.raises(ValidationError, match="requires at least 1 proposal"):
        TrialResult(
            label=TrialLabel.A,
            selected_evidence_ids=selected,
            proposals=(),
        )
    with pytest.raises(ValidationError, match="at most 20 proposals"):
        TrialResult(
            label=TrialLabel.A,
            selected_evidence_ids=selected,
            proposals=tuple(
                _proposal(
                    decision=ProposalDecision.CREATE,
                    proposal_id=f"proposal_{index}",
                )
                for index in range(MAX_PROPOSALS_PER_TRIAL + 1)
            ),
        )


def test_input_contract_rejects_raw_bodies_credentials_and_extra_records():
    with pytest.raises(ValidationError, match="Extra inputs"):
        DimensionEvidence.model_validate(
            {
                "dimension": "trigger",
                "status": "unknown",
                "evidence_ids": [],
                "raw_note_body": "private source text",
                "api_key": "sk-proj-" + ("a" * 24),
                "records": [{"selected": False}],
            }
        )


def test_comparison_requires_b_to_retain_a_selection_and_same_proposals():
    proposal = _proposal(
        decision=ProposalDecision.CREATE,
        evidence=_evidence(
            supported={EvidenceDimension.TRIGGER: ("evidence_one",)}
        ),
    )
    trial_a = _trial(TrialLabel.A, proposal, selected=("evidence_one",))
    trial_b_proposal = _proposal(
        decision=ProposalDecision.CREATE,
        evidence=_evidence(
            supported={EvidenceDimension.TRIGGER: ("evidence_two",)}
        ),
    )
    trial_b = _trial(
        TrialLabel.B,
        trial_b_proposal,
        selected=("evidence_two",),
    )

    with pytest.raises(ValidationError, match="retain every evidence selection"):
        CrossSessionComparison(trial_a=trial_a, trial_b=trial_b)

    missing_b_proposal = _proposal(
        proposal_id="proposal_two",
        decision=ProposalDecision.CREATE,
    )
    different_b = TrialResult(
        label=TrialLabel.B,
        selected_evidence_ids=("evidence_one",),
        proposals=(missing_b_proposal,),
    )
    with pytest.raises(ValidationError, match="same proposal_id"):
        CrossSessionComparison(trial_a=trial_a, trial_b=different_b)


def test_comparison_rejects_different_targets_for_paired_updates():
    trial_a = _trial(
        TrialLabel.A,
        _proposal(
            decision=ProposalDecision.UPDATE,
            existing_skill_id="skill_one",
        ),
        selected=("evidence_one",),
    )
    trial_b = _trial(
        TrialLabel.B,
        _proposal(
            decision=ProposalDecision.UPDATE,
            existing_skill_id="skill_two",
        ),
        selected=("evidence_one",),
    )

    with pytest.raises(ValidationError, match="same existing_skill_id"):
        CrossSessionComparison(trial_a=trial_a, trial_b=trial_b)


def test_report_is_deterministic_and_preserves_unknown():
    trial_a_proposal = _proposal(
        decision=ProposalDecision.CREATE,
        evidence=_evidence(
            supported={EvidenceDimension.TRIGGER: ("memo_trigger",)}
        ),
    )
    trial_b_proposal = _proposal(
        decision=ProposalDecision.UPDATE,
        existing_skill_id="skill_existing",
        evidence=_evidence(
            supported={
                EvidenceDimension.TRIGGER: ("memo_trigger",),
                EvidenceDimension.DO_NOT_USE: ("record_boundary",),
                EvidenceDimension.SAFETY: ("record_safety",),
            }
        ),
    )
    comparison = CrossSessionComparison(
        trial_a=_trial(
            TrialLabel.A,
            trial_a_proposal,
            selected=("memo_trigger",),
        ),
        trial_b=_trial(
            TrialLabel.B,
            trial_b_proposal,
            selected=("record_safety", "memo_trigger", "record_boundary"),
        ),
    )

    first = render_cross_session_markdown(comparison)
    second = render_cross_session_markdown(comparison)

    assert first == second
    assert "| Decision | `create` | `update` |" in first
    assert "| `trigger` | `supported` (1 selected source(s)) |" in first
    assert "| `do_not_use` | `unknown` |" in first
    assert "`newly_supported`" in first
    assert "| `decision` | `unknown` | `unknown` | `unknown` |" in first
    assert "memo_trigger" not in first
    assert "record_boundary" not in first
    assert "proposal_one" not in first
    assert "skill_existing" not in first
    assert "private source text" not in first
    assert first.endswith("\n")


def test_report_renders_inferred_and_needs_confirmation_distinctly():
    def evidence_for(status_by_dimension):
        return tuple(
            DimensionEvidence(
                dimension=dimension,
                status=status_by_dimension.get(dimension, EvidenceStatus.UNKNOWN),
            )
            for dimension in EvidenceDimension
        )

    trial_a_proposal = _proposal(
        decision=ProposalDecision.NO_SKILL,
        no_skill_destination=NoSkillDestination.NONE,
        evidence=evidence_for(
            {EvidenceDimension.DECISION: EvidenceStatus.INFERRED}
        ),
    )
    trial_b_proposal = _proposal(
        decision=ProposalDecision.NO_SKILL,
        no_skill_destination=NoSkillDestination.NONE,
        evidence=evidence_for(
            {EvidenceDimension.DECISION: EvidenceStatus.NEEDS_CONFIRMATION}
        ),
    )
    comparison = CrossSessionComparison(
        trial_a=_trial(TrialLabel.A, trial_a_proposal, selected=("evidence_one",)),
        trial_b=_trial(TrialLabel.B, trial_b_proposal, selected=("evidence_one",)),
    )

    report = render_cross_session_markdown(comparison)

    assert (
        "| `decision` | `inferred` | `needs_confirmation` | "
        "`needs_confirmation` |"
    ) in report
    assert report == render_cross_session_markdown(comparison)


def test_opaque_identifier_contract_rejects_paths_and_token_like_values():
    for unsafe in (
        r"C:\Users\name\note.md",
        "../note",
        "sk-proj-" + ("a" * 24),
        "contains spaces",
    ):
        with pytest.raises(ValidationError, match="opaque lowercase identifier"):
            DimensionEvidence(
                dimension=EvidenceDimension.TRIGGER,
                status=EvidenceStatus.SUPPORTED,
                evidence_ids=(unsafe,),
            )
