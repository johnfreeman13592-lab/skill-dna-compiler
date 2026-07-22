from __future__ import annotations

from pathlib import Path

import pytest

from skill_dna_compiler.vault.parser import MarkdownParseError, parse_markdown_file
from skill_dna_compiler.vault.scanner import scan_vault


def _scanned_file(tmp_path: Path, content: str):
    note = tmp_path / "Vault" / "Note.md"
    note.parent.mkdir(parents=True)
    note.write_text(content, encoding="utf-8")
    return scan_vault(note.parent)[0]


def test_parse_frontmatter_sections_and_internal_links(tmp_path):
    vault_file = _scanned_file(
        tmp_path,
        """---
title: Example
tags:
  - reusable
---
# First
Use [[Target Note#Details|the target]].

```text
[[Ignored In Code]]
```

## Second
Also see [[Plain Note]] and ![[Ignored Embed]].
""",
    )

    parsed = parse_markdown_file(vault_file)

    assert parsed.frontmatter == {"title": "Example", "tags": ["reusable"]}
    assert [section.heading for section in parsed.sections] == ["First", "Second"]
    assert [link.target for link in parsed.internal_links] == ["Target Note", "Plain Note"]
    assert parsed.internal_links[0].heading == "Details"
    assert parsed.internal_links[0].alias == "the target"


def test_parse_rejects_invalid_frontmatter(tmp_path):
    vault_file = _scanned_file(tmp_path, "---\ntags: [broken\n---\nBody")

    with pytest.raises(MarkdownParseError, match="valid YAML"):
        parse_markdown_file(vault_file)


def test_parse_enforces_size_limit(tmp_path):
    vault_file = _scanned_file(tmp_path, "long content")

    with pytest.raises(MarkdownParseError, match="size limit"):
        parse_markdown_file(vault_file, max_bytes=2)

