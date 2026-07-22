from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from skill_dna_compiler.domain import SkillDNA
from skill_dna_compiler.storage.repositories import ExportRepository


@dataclass(frozen=True)
class ExportPlan:
    skill_dna: SkillDNA
    approved_root: Path
    skill_directory: Path
    skill_file: Path
    content: str
    overwrites_existing: bool


def render_skill_md(skill_dna: SkillDNA) -> str:
    description_parts = [skill_dna.description.strip()]
    if skill_dna.triggers:
        description_parts.append(
            "Use when " + "; ".join(_trim_list_punctuation(skill_dna.triggers)) + "."
        )
    if skill_dna.do_not_use_when:
        description_parts.append(
            "Do not use when "
            + "; ".join(_trim_list_punctuation(skill_dna.do_not_use_when))
            + "."
        )
    description = " ".join(description_parts).replace("<", "(").replace(">", ")")
    if len(description) > 1024:
        raise ValueError("Skill description exceeds the Codex 1024-character limit")
    frontmatter = yaml.safe_dump(
        {"name": skill_dna.slug, "description": description},
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    ).strip()
    sections = [f"---\n{frontmatter}\n---", f"# {skill_dna.name}"]
    _append_list(sections, "Principles", skill_dna.principles)
    if skill_dna.workflow:
        sections.append("## Workflow\n\n" + "\n".join(
            f"{index}. {step.action}"
            for index, step in enumerate(skill_dna.workflow, start=1)
        ))
    _append_list(sections, "Constraints", skill_dna.constraints)
    _append_list(sections, "Do not use when", skill_dna.do_not_use_when)
    if skill_dna.sources:
        source_lines = []
        for source in skill_dna.sources:
            source_lines.extend(
                [
                    f"- `{source.document_id}` — {source.reason}",
                    f"  > {source.quote.replace(chr(10), chr(10) + '  > ')}",
                ]
            )
        sections.append("## Source references\n\n" + "\n".join(source_lines))
    return "\n\n".join(sections).rstrip() + "\n"


def _trim_list_punctuation(items: list[str]) -> list[str]:
    return [item.strip().rstrip(".;") for item in items]


def _append_list(sections: list[str], heading: str, items: list[str]) -> None:
    if items:
        sections.append(f"## {heading}\n\n" + "\n".join(f"- {item}" for item in items))


class SkillExportService:
    def __init__(self, repository: ExportRepository) -> None:
        self._repository = repository

    def prepare(self, skill_dna: SkillDNA, destination_root: Path) -> ExportPlan:
        self._repository.assert_exportable(skill_dna)
        root = destination_root.expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError("The approved export destination must be a directory")
        skill_directory = root / skill_dna.slug
        if skill_directory.is_symlink():
            raise ValueError("A symbolic-link Skill directory is not allowed")
        resolved_directory = skill_directory.resolve(strict=False)
        try:
            resolved_directory.relative_to(root)
        except ValueError as exc:
            raise ValueError("The Skill directory escapes the approved destination") from exc
        skill_file = resolved_directory / "SKILL.md"
        if skill_file.is_symlink():
            raise ValueError("A symbolic-link SKILL.md is not allowed")
        return ExportPlan(
            skill_dna=skill_dna,
            approved_root=root,
            skill_directory=resolved_directory,
            skill_file=skill_file,
            content=render_skill_md(skill_dna),
            overwrites_existing=skill_file.exists(),
        )

    def export(self, plan: ExportPlan, *, overwrite: bool = False) -> Path:
        refreshed = self.prepare(plan.skill_dna, plan.approved_root)
        if refreshed.skill_file != plan.skill_file or refreshed.content != plan.content:
            raise ValueError("The export plan changed; preview it again")
        if refreshed.overwrites_existing and not overwrite:
            raise FileExistsError("SKILL.md already exists; explicit overwrite is required")
        directory_existed = refreshed.skill_directory.exists()
        refreshed.skill_directory.mkdir(parents=False, exist_ok=True)
        previous_content = (
            refreshed.skill_file.read_bytes() if refreshed.skill_file.exists() else None
        )
        try:
            _atomic_replace_bytes(refreshed.skill_file, refreshed.content.encode("utf-8"))
            self._repository.record_export(
                refreshed.skill_dna,
                destination_path=refreshed.skill_file,
            )
        except Exception as export_error:
            try:
                if previous_content is None:
                    refreshed.skill_file.unlink(missing_ok=True)
                else:
                    _atomic_replace_bytes(refreshed.skill_file, previous_content)
                if not directory_existed and refreshed.skill_directory.exists():
                    refreshed.skill_directory.rmdir()
            except Exception as rollback_error:
                raise RuntimeError(
                    "Export history failed and the destination could not be restored"
                ) from rollback_error
            raise export_error
        return refreshed.skill_file


def _atomic_replace_bytes(destination: Path, content: bytes) -> None:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=destination.parent,
                prefix=".skill-dna-",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            temporary_path.replace(destination)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
