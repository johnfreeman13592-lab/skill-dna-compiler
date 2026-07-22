from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from skill_dna_compiler.vault.models import VaultFile

DEFAULT_EXCLUDED_DIRS = frozenset({".git", ".obsidian", ".trash", "node_modules"})


class VaultScanError(ValueError):
    """Raised when a Vault cannot be scanned safely."""


def _is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction and is_junction())


def _resolves_within(path: Path, root: Path) -> bool:
    try:
        return path.resolve(strict=True).is_relative_to(root)
    except OSError:
        return False


def _normalize_exclusions(exclude_paths: tuple[str, ...]) -> frozenset[str]:
    normalized: set[str] = set(DEFAULT_EXCLUDED_DIRS)
    for raw in exclude_paths:
        path = PurePosixPath(raw.replace("\\", "/").strip("/"))
        if path.is_absolute() or ".." in path.parts:
            raise VaultScanError(f"Invalid exclusion path: {raw}")
        if path.as_posix() not in {"", "."}:
            normalized.add(path.as_posix())
    return frozenset(normalized)


def _is_excluded(relative_path: str, exclusions: frozenset[str]) -> bool:
    path = PurePosixPath(relative_path)
    for excluded in exclusions:
        excluded_parts = PurePosixPath(excluded).parts
        if len(excluded_parts) == 1 and excluded_parts[0] in path.parts:
            return True
        if path.parts[: len(excluded_parts)] == excluded_parts:
            return True
    return False


def hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_vault(
    root: Path,
    *,
    exclude_paths: tuple[str, ...] = (),
    max_files: int = 10_000,
) -> list[VaultFile]:
    """Discover Markdown files without following links or modifying the Vault."""

    if max_files < 1:
        raise VaultScanError("max_files must be at least 1")

    try:
        resolved_root = root.expanduser().resolve(strict=True)
    except OSError as exc:
        raise VaultScanError(f"Vault does not exist or cannot be accessed: {root}") from exc
    if not resolved_root.is_dir():
        raise VaultScanError(f"Vault path is not a directory: {resolved_root}")

    exclusions = _normalize_exclusions(exclude_paths)
    discovered: list[VaultFile] = []

    for current_root, directory_names, file_names in os.walk(
        resolved_root, topdown=True, followlinks=False
    ):
        current_path = Path(current_root)
        kept_directories: list[str] = []
        for name in directory_names:
            directory = current_path / name
            relative = directory.relative_to(resolved_root).as_posix()
            if (
                not _is_link_or_junction(directory)
                and _resolves_within(directory, resolved_root)
                and not _is_excluded(relative, exclusions)
            ):
                kept_directories.append(name)
        directory_names[:] = kept_directories

        for name in file_names:
            if Path(name).suffix.lower() != ".md":
                continue
            path = current_path / name
            if _is_link_or_junction(path) or not _resolves_within(path, resolved_root):
                continue
            relative = path.relative_to(resolved_root).as_posix()
            if _is_excluded(relative, exclusions):
                continue
            try:
                stat = path.stat()
                discovered.append(
                    VaultFile(
                        absolute_path=path.resolve(strict=True),
                        relative_path=relative,
                        title=path.stem,
                        size_bytes=stat.st_size,
                        modified_at=datetime.fromtimestamp(stat.st_mtime, UTC),
                        content_hash=hash_file(path),
                    )
                )
            except OSError as exc:
                raise VaultScanError(f"Could not read Markdown file: {relative}") from exc
            if len(discovered) > max_files:
                raise VaultScanError(
                    f"Vault contains more than the configured limit of {max_files} Markdown files"
                )

    return sorted(discovered, key=lambda item: item.relative_path.casefold())
