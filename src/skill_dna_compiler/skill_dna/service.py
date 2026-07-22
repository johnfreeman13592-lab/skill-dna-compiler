from __future__ import annotations

import re
import unicodedata

from skill_dna_compiler.domain import CandidateStatus, SkillDNA
from skill_dna_compiler.review import TRACE_POLICY_VERSION, require_valid_instruction_traces
from skill_dna_compiler.storage.repositories import ExtractionRepository, SkillDNARepository


def suggest_slug(name: str, candidate_id: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    if slug:
        return slug[:64].rstrip("-")
    suffix = re.sub(r"[^a-z0-9]", "", candidate_id.lower())[-12:] or "candidate"
    return f"skill-{suffix}"


class SkillDNAService:
    def __init__(self, candidates: ExtractionRepository, skills: SkillDNARepository) -> None:
        self._candidates = candidates
        self._skills = skills

    def convert_approved_candidate(self, candidate_id: str) -> SkillDNA:
        return self._skills.save_version(self.preview_approved_candidate(candidate_id))

    def preview_approved_candidate(self, candidate_id: str) -> SkillDNA:
        saved = self._candidates.get_candidate(candidate_id)
        if saved.status is not CandidateStatus.APPROVED:
            raise ValueError("Only an approved candidate can become Skill DNA")
        require_valid_instruction_traces(saved.candidate, saved.instruction_traces)
        existing = self._skills.get_by_candidate(candidate_id)
        version = "0.1.0" if existing is None else _next_patch(existing.version)
        slug = existing.slug if existing else self._available_slug(
            suggest_slug(saved.candidate.name, saved.id), saved.id
        )
        data = saved.candidate
        values = {
            "candidate_id": saved.id,
            "trace_policy_version": TRACE_POLICY_VERSION,
            "name": data.name,
            "slug": slug,
            "description": data.description,
            "version": version,
            "triggers": data.triggers,
            "do_not_use_when": data.do_not_use_when,
            "principles": data.principles,
            "workflow": data.workflow,
            "constraints": data.constraints,
            "sources": [source.model_dump(mode="json") for source in data.source_references],
            "instruction_traces": [
                trace.model_dump(mode="json") for trace in saved.instruction_traces
            ],
            "created_at": existing.created_at if existing else saved.created_at,
        }
        if existing:
            values["id"] = existing.id
        return SkillDNA.model_validate(values)

    def _available_slug(self, preferred: str, candidate_id: str) -> str:
        if not self._skills.slug_exists(preferred):
            return preferred
        suffix = re.sub(r"[^a-z0-9]", "", candidate_id.lower())[-8:] or "candidate"
        return f"{preferred[: 63 - len(suffix)].rstrip('-')}-{suffix}"


def _next_patch(version: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"
