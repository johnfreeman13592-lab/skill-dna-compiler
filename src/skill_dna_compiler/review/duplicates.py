from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from skill_dna_compiler.extraction.schemas import (
    ExtractedCandidate,
    ExtractedSourceReference,
)


@dataclass(frozen=True)
class DuplicateCandidatePair:
    left_id: str
    right_id: str
    score: float
    reasons: tuple[str, ...]


def find_duplicate_candidates(
    candidates: Sequence[tuple[str, ExtractedCandidate]],
    *,
    threshold: float = 0.62,
) -> list[DuplicateCandidatePair]:
    if not 0 <= threshold <= 1:
        raise ValueError("Duplicate threshold must be between 0 and 1")

    matches: list[DuplicateCandidatePair] = []
    for index, (left_id, left) in enumerate(candidates):
        for right_id, right in candidates[index + 1 :]:
            if left_id == right_id:
                continue
            name_score = _text_similarity(left.name, right.name)
            description_score = _text_similarity(left.description, right.description)
            guidance_score = _text_similarity(
                _guidance_text(left), _guidance_text(right)
            )
            source_score = _set_overlap(
                {reference.document_id for reference in left.source_references},
                {reference.document_id for reference in right.source_references},
            )
            score = (
                0.45 * name_score
                + 0.20 * description_score
                + 0.25 * guidance_score
                + 0.10 * source_score
            )
            if score < threshold:
                continue
            reasons: list[str] = []
            if name_score >= 0.75:
                reasons.append("候補名が類似")
            if description_score >= 0.65:
                reasons.append("説明が類似")
            if guidance_score >= 0.55:
                reasons.append("手順・原則などが重複")
            if source_score > 0:
                reasons.append("出典文書が重複")
            if not reasons:
                reasons.append("総合類似度が確認基準以上")
            matches.append(
                DuplicateCandidatePair(
                    left_id=left_id,
                    right_id=right_id,
                    score=round(score, 4),
                    reasons=tuple(reasons),
                )
            )
    return sorted(matches, key=lambda match: match.score, reverse=True)


def merge_candidate_data(
    primary: ExtractedCandidate, secondary: ExtractedCandidate
) -> ExtractedCandidate:
    warnings = _merge_text_items(primary.warnings, secondary.warnings)
    warnings = _merge_text_items(
        warnings,
        ["2件の候補を手動統合しました。承認前に内容を確認してください。"],
    )
    if primary.category != secondary.category:
        warnings = _merge_text_items(
            warnings,
            [f"カテゴリが異なるため、主候補の'{primary.category}'を保持しました。"],
        )
    if primary.generality != secondary.generality:
        warnings = _merge_text_items(
            warnings,
            [f"汎用性が異なるため、主候補の'{primary.generality}'を保持しました。"],
        )

    actions = _merge_text_items(
        [step.action for step in primary.workflow],
        [step.action for step in secondary.workflow],
    )
    sources = _merge_sources(primary.source_references, secondary.source_references)
    return ExtractedCandidate.model_validate(
        {
            "name": primary.name,
            "description": primary.description,
            "category": primary.category,
            "generality": primary.generality,
            "triggers": _merge_text_items(primary.triggers, secondary.triggers),
            "do_not_use_when": _merge_text_items(
                primary.do_not_use_when, secondary.do_not_use_when
            ),
            "principles": _merge_text_items(primary.principles, secondary.principles),
            "workflow": [
                {"order": index, "action": action}
                for index, action in enumerate(actions, start=1)
            ],
            "constraints": _merge_text_items(
                primary.constraints, secondary.constraints
            ),
            "source_references": [source.model_dump(mode="json") for source in sources],
            "confidence": min(primary.confidence, secondary.confidence),
            "confidence_reason": (
                "手動統合のため、元候補のうち低い信頼度を採用しました。"
                f"主候補: {primary.confidence_reason} 統合元: {secondary.confidence_reason}"
            ),
            "warnings": warnings,
        }
    )


def _guidance_text(candidate: ExtractedCandidate) -> str:
    return " ".join(
        [
            *candidate.triggers,
            *candidate.do_not_use_when,
            *candidate.principles,
            *(step.action for step in candidate.workflow),
            *candidate.constraints,
        ]
    )


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _text_similarity(left: str, right: str) -> float:
    left_grams = _character_grams(_normalize(left))
    right_grams = _character_grams(_normalize(right))
    return _set_overlap(left_grams, right_grams)


def _character_grams(value: str) -> set[str]:
    if not value:
        return set()
    if len(value) == 1:
        return {value}
    return {value[index : index + 2] for index in range(len(value) - 1)}


def _set_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return 2 * len(left & right) / (len(left) + len(right))


def _merge_text_items(primary: Sequence[str], secondary: Sequence[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in [*primary, *secondary]:
        key = _normalize(item)
        if key and key not in seen:
            seen.add(key)
            merged.append(item)
    return merged


def _merge_sources(
    primary: Sequence[ExtractedSourceReference],
    secondary: Sequence[ExtractedSourceReference],
) -> list[ExtractedSourceReference]:
    merged: list[ExtractedSourceReference] = []
    seen: set[tuple[str, str, str]] = set()
    for source in [*primary, *secondary]:
        key = (source.document_id, source.quote, source.reason)
        if key not in seen:
            seen.add(key)
            merged.append(source)
    return merged
