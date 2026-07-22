from __future__ import annotations

from pathlib import Path

import pytest

from skill_dna_compiler.vault.scanner import VaultScanError, scan_vault


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_vault_discovers_markdown_and_preserves_files(tmp_path):
    vault = tmp_path / "Vault"
    _write(vault / "Root.md", "root")
    _write(vault / "notes" / "Nested.MD", "nested")
    _write(vault / "notes" / "ignore.txt", "not markdown")
    _write(vault / ".obsidian" / "workspace.md", "internal")
    _write(vault / "private" / "Secret.md", "private")
    before = {path: path.read_bytes() for path in vault.rglob("*") if path.is_file()}

    result = scan_vault(vault, exclude_paths=("private",))

    assert [item.relative_path for item in result] == ["notes/Nested.MD", "Root.md"]
    assert all(len(item.content_hash) == 64 for item in result)
    after = {path: path.read_bytes() for path in vault.rglob("*") if path.is_file()}
    assert after == before


def test_scan_vault_rejects_invalid_root(tmp_path):
    with pytest.raises(VaultScanError, match="does not exist"):
        scan_vault(tmp_path / "missing")


def test_scan_vault_enforces_file_limit(tmp_path):
    vault = tmp_path / "Vault"
    _write(vault / "one.md", "1")
    _write(vault / "two.md", "2")

    with pytest.raises(VaultScanError, match="configured limit"):
        scan_vault(vault, max_files=1)


def test_scan_vault_excludes_nested_relative_path(tmp_path):
    vault = tmp_path / "Vault"
    _write(vault / "projects" / "private" / "hidden.md", "hidden")
    _write(vault / "projects" / "public" / "visible.md", "visible")

    result = scan_vault(vault, exclude_paths=("projects/private",))

    assert [item.relative_path for item in result] == ["projects/public/visible.md"]
