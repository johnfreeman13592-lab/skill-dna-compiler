from __future__ import annotations

import re
from typing import Any

import yaml

from skill_dna_compiler.vault.models import (
    DocumentSection,
    InternalLink,
    ParsedNote,
    VaultFile,
)

_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_INTERNAL_LINK_PATTERN = re.compile(r"(?<!!)\[\[([^\]\n]+)\]\]")
_FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")


class MarkdownParseError(ValueError):
    """Raised when a Markdown note cannot be parsed safely."""


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str, int]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, 1

    closing_line = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() in {"---", "..."}),
        None,
    )
    if closing_line is None:
        raise MarkdownParseError("Frontmatter starts with '---' but has no closing delimiter")

    raw_frontmatter = "\n".join(lines[1:closing_line])
    try:
        loaded = yaml.safe_load(raw_frontmatter) if raw_frontmatter.strip() else {}
    except yaml.YAMLError as exc:
        raise MarkdownParseError("Frontmatter is not valid YAML") from exc
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise MarkdownParseError("Frontmatter must be a YAML mapping")

    body = "\n".join(lines[closing_line + 1 :])
    return loaded, body, closing_line + 2


def _line_is_inside_fence(lines: list[str]) -> list[bool]:
    results: list[bool] = []
    active_fence: str | None = None
    for line in lines:
        match = _FENCE_PATTERN.match(line)
        results.append(active_fence is not None)
        if match:
            marker = match.group(1)[0]
            if active_fence is None:
                active_fence = marker
            elif active_fence == marker:
                active_fence = None
    return results


def _parse_sections(body: str, first_body_line: int) -> list[DocumentSection]:
    lines = body.splitlines()
    fenced = _line_is_inside_fence(lines)
    headings: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        if fenced[index]:
            continue
        match = _HEADING_PATTERN.match(line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))

    sections: list[DocumentSection] = []
    for position, (line_index, level, heading) in enumerate(headings):
        next_index = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        content = "\n".join(lines[line_index + 1 : next_index]).strip()
        sections.append(
            DocumentSection(
                heading=heading,
                level=level,
                start_line=first_body_line + line_index,
                end_line=max(first_body_line + line_index, first_body_line + next_index - 1),
                content=content,
            )
        )
    return sections


def _parse_internal_links(body: str, first_body_line: int) -> list[InternalLink]:
    links: list[InternalLink] = []
    fenced = _line_is_inside_fence(body.splitlines())
    for line_index, line in enumerate(body.splitlines()):
        if fenced[line_index]:
            continue
        for match in _INTERNAL_LINK_PATTERN.finditer(line):
            raw = match.group(1).strip()
            target_and_heading, separator, alias = raw.partition("|")
            target, heading_separator, heading = target_and_heading.partition("#")
            if not target.strip():
                continue
            links.append(
                InternalLink(
                    raw=raw,
                    target=target.strip(),
                    heading=heading.strip() if heading_separator and heading.strip() else None,
                    alias=alias.strip() if separator and alias.strip() else None,
                    line=first_body_line + line_index,
                )
            )
    return links


def parse_markdown_file(vault_file: VaultFile, *, max_bytes: int = 2_000_000) -> ParsedNote:
    if vault_file.size_bytes > max_bytes:
        raise MarkdownParseError(
            f"Markdown file exceeds the configured size limit of {max_bytes} bytes"
        )
    try:
        text = vault_file.absolute_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        message = f"Could not read UTF-8 Markdown: {vault_file.relative_path}"
        raise MarkdownParseError(message) from exc

    frontmatter, body, first_body_line = _split_frontmatter(text)
    return ParsedNote(
        file=vault_file,
        source_text=text,
        frontmatter=frontmatter,
        body=body,
        sections=_parse_sections(body, first_body_line),
        internal_links=_parse_internal_links(body, first_body_line),
    )
