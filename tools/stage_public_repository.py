"""Create and audit a history-free public repository staging tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT_FILES = (
    ".env.example",
    ".gitattributes",
    ".gitignore",
    "app.py",
    "CONTRIBUTING.md",
    "LICENSE",
    "pyproject.toml",
    "README.md",
    "README.ja.md",
    "README.zh-CN.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
)
PUBLIC_TREES = (".github", "packaging", "src", "tests", "tools")
PUBLIC_DOCS = (
    "architecture.md",
    "beta-completion-audit.md",
    "beta-quick-start.md",
    "beta-test-checklist.md",
    "cross-session-skill-discovery-experiment.md",
    "dependency-license-audit-2026-07-22.md",
    "implementation-plan.md",
    "post-beta-roadmap.md",
    "privacy.md",
    "public-beta-readiness-audit-2026-07-22.md",
)
ALLOWED_SUFFIXES = {
    "",
    ".cmd",
    ".example",
    ".gitattributes",
    ".gitignore",
    ".md",
    ".ps1",
    ".py",
    ".spec",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}
PRIVATE_MARKERS = (
    re.compile(r"\bRyoki\b", re.IGNORECASE),
    re.compile(r"Shared Memory Layer", re.IGNORECASE),
    re.compile(r"DEVELOPMENT_NOTES\.md", re.IGNORECASE),
    re.compile(r"docs[/\\]handoff-", re.IGNORECASE),
    re.compile(r"OneDrive[/\\]+ドキュメント[/\\]+Skill DNA Compiler", re.IGNORECASE),
)
CREDENTIAL_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
EXPECTED_SCANNER_FIXTURES = {
    "tests/unit/test_public_repository_stager.py",
    "tools/stage_public_repository.py",
}
GENERATED_DIRECTORY_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache"}
SYNTHETIC_CREDENTIAL_FILES = {
    "tests/unit/test_app.py",
    "tests/unit/test_credentials.py",
    "tests/unit/test_logging_config.py",
    "tests/unit/test_payloads.py",
    "tests/unit/test_public_repository_stager.py",
    "tests/unit/test_sensitive_data.py",
    "tests/unit/test_settings.py",
}


class PublicStagingError(RuntimeError):
    """The public staging tree could not be safely created."""


@dataclass(frozen=True)
class StagedFile:
    path: str
    size: int
    sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_files(project_root: Path, relative_root: str) -> list[Path]:
    root = project_root / relative_root
    if not root.is_dir():
        raise PublicStagingError(f"Required public tree is missing: {relative_root}")
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(project_root)
        if (
            any(
                part in GENERATED_DIRECTORY_NAMES or part.endswith(".egg-info")
                for part in relative.parts
            )
            or path.name.endswith((".pyc", ".pyo"))
        ):
            continue
        if path.is_symlink():
            raise PublicStagingError(f"Symbolic links are not allowed: {relative.as_posix()}")
        if path.is_file():
            files.append(path)
    return files


def collect_public_files(project_root: Path) -> list[Path]:
    project_root = project_root.resolve(strict=True)
    files: list[Path] = []
    for relative in ROOT_FILES:
        path = project_root / relative
        if not path.is_file() or path.is_symlink():
            raise PublicStagingError(f"Required public file is missing or unsafe: {relative}")
        files.append(path)
    for name in PUBLIC_DOCS:
        path = project_root / "docs" / name
        if not path.is_file() or path.is_symlink():
            raise PublicStagingError(f"Required public document is missing or unsafe: docs/{name}")
        files.append(path)
    for relative_root in PUBLIC_TREES:
        files.extend(_tree_files(project_root, relative_root))

    unique = {path.relative_to(project_root).as_posix(): path for path in files}
    if len(unique) != len(files):
        raise PublicStagingError("The public allowlist produced duplicate paths")
    return [unique[name] for name in sorted(unique)]


def _scan_text(relative: str, text: str) -> list[str]:
    findings: list[str] = []
    for pattern in PRIVATE_MARKERS:
        if pattern.search(text) and relative not in EXPECTED_SCANNER_FIXTURES:
            findings.append(f"private marker matched {pattern.pattern!r}")
    credential_matches = [
        pattern.pattern for pattern in CREDENTIAL_PATTERNS if pattern.search(text)
    ]
    if credential_matches and relative not in SYNTHETIC_CREDENTIAL_FILES:
        findings.append("credential-like value outside reviewed synthetic fixtures")
    return findings


def audit_public_files(project_root: Path, files: list[Path]) -> list[StagedFile]:
    audited: list[StagedFile] = []
    failures: list[str] = []
    for path in files:
        relative = path.relative_to(project_root).as_posix()
        suffix = path.suffix.lower() or (path.name if path.name.startswith(".") else "")
        if suffix not in ALLOWED_SUFFIXES:
            failures.append(f"{relative}: unsupported public file type {suffix!r}")
            continue
        data = path.read_bytes()
        if b"\x00" in data:
            failures.append(f"{relative}: binary content is not allowed")
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            failures.append(f"{relative}: content is not valid UTF-8")
            continue
        failures.extend(f"{relative}: {finding}" for finding in _scan_text(relative, text))
        audited.append(StagedFile(relative, len(data), hashlib.sha256(data).hexdigest()))
    if failures:
        raise PublicStagingError("Public-source audit failed:\n- " + "\n- ".join(failures))
    return audited


def stage_public_repository(
    project_root: Path,
    destination: Path,
    report_path: Path,
) -> dict[str, object]:
    project_root = project_root.resolve(strict=True)
    destination = destination.resolve(strict=False)
    report_path = report_path.resolve(strict=False)
    build_root = (project_root / "build").resolve(strict=False)
    if destination.exists():
        raise PublicStagingError(f"Refusing to overwrite existing destination: {destination}")
    if report_path.exists():
        raise PublicStagingError(f"Refusing to overwrite existing report: {report_path}")
    if build_root not in destination.parents:
        raise PublicStagingError("Destination must be a new directory under the project build path")
    if report_path != build_root and build_root not in report_path.parents:
        raise PublicStagingError("Report must stay under the project build path")
    if report_path == destination or destination in report_path.parents:
        raise PublicStagingError("Report must remain outside the staged public tree")

    files = collect_public_files(project_root)
    audited = audit_public_files(project_root, files)

    destination.mkdir(parents=True)
    for source, item in zip(files, audited, strict=True):
        target = destination / item.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if _sha256(target) != item.sha256:
            raise PublicStagingError(f"Copied file hash mismatch: {item.path}")

    report = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "pass",
        "source": str(project_root),
        "destination": str(destination),
        "history_included": False,
        "file_count": len(audited),
        "files": [asdict(item) for item in audited],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path("build/public-repository-staging-20260722"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("build/public-repository-staging-20260722.audit.json"),
    )
    args = parser.parse_args(argv)
    try:
        report = stage_public_repository(Path.cwd(), args.destination, args.report)
    except (OSError, PublicStagingError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "file_count": report["file_count"],
                "destination": report["destination"],
                "report": str(args.report.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
