"""Offline verification for a packaged Skill DNA Compiler Windows candidate.

The verifier deliberately uses only the Python standard library.  It never
connects to a non-loopback address and refuses to overwrite existing reports.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

ROOT_NAME = "Skill DNA Compiler"
EXECUTABLE_NAME = "Skill DNA Compiler.exe"
SMOKE_ENV = "SKILL_DNA_PACKAGE_SMOKE_TEST"
SMOKE_MARKER = "SKILL_DNA_PACKAGE_IMPORTS_OK"
HEADLESS_ENV = "SKILL_DNA_LAUNCHER_HEADLESS"
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "[::1]"}
REQUIRED_FILES = (
    EXECUTABLE_NAME,
    "README.txt",
    "_internal/streamlit/static/index.html",
    "docs/beta-quick-start.md",
    "docs/beta-quick-start.ja.md",
    "docs/beta-test-checklist.md",
    "docs/privacy.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "THIRD_PARTY_LICENSES/streamlit-1.59.2/LICENSE",
    "THIRD_PARTY_LICENSES/streamlit-1.59.2/NOTICES",
    "THIRD_PARTY_LICENSES/python-packages/manifest.json",
    "dependency-versions.txt",
)
FORBIDDEN_NAMES = {".env", ".env.local", "skill-dna.db", "skill.md"}
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
DEPENDENCY_LINE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*==[^\s]+$")
CHECKSUM_LINE = re.compile(r"^([0-9A-Fa-f]{64})(?:\s+\*?(.+))?$")
BETA_ARCHIVE_NAME = re.compile(
    r"^skill-dna-compiler-(\d+\.\d+\.\d+)-beta\.(\d+)"
    r"(?:-[0-9A-Za-z.-]+)?-windows-x64\.zip$"
)
MAX_ZIP_ENTRIES = 30_000
MAX_UNCOMPRESSED_BYTES = 500_000_000
MAX_MEMBER_BYTES = 100_000_000
MAX_COMPRESSION_RATIO = 100


class ToolRuntimeError(RuntimeError):
    """The verifier could not perform a requested check."""


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class Listener:
    host: str
    port: int
    pid: int


@dataclass
class VerificationReport:
    archive: str
    archive_sha256: str
    generated_at: str
    status: str
    checks: list[Check]

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "archive": self.archive,
            "archive_sha256": self.archive_sha256,
            "generated_at": self.generated_at,
            "status": self.status,
            "checks": [asdict(check) for check in self.checks],
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_member_path(name: str) -> PurePosixPath | None:
    normalized = name.replace("\\", "/")
    if "\x00" in normalized or normalized.startswith("/"):
        return None
    path = PurePosixPath(normalized)
    if not path.parts or path.parts[0].endswith(":") or ".." in path.parts:
        return None
    return path


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


def _checksum_check(archive: Path, checksum_path: Path, actual: str) -> Check:
    if not checksum_path.is_file():
        return Check("sha256_sidecar", False, f"Sidecar not found: {checksum_path.name}")
    try:
        lines = [line.strip() for line in checksum_path.read_text("utf-8-sig").splitlines()]
    except (OSError, UnicodeError) as exc:
        return Check("sha256_sidecar", False, f"Could not read sidecar: {exc}")
    lines = [line for line in lines if line]
    match = CHECKSUM_LINE.fullmatch(lines[0]) if len(lines) == 1 else None
    if not match:
        return Check("sha256_sidecar", False, "Sidecar must contain one SHA-256 line")
    expected, recorded_name = match.groups()
    if recorded_name and Path(recorded_name).name != archive.name:
        return Check("sha256_sidecar", False, "Sidecar filename does not match the archive")
    if expected.lower() != actual:
        return Check("sha256_sidecar", False, "SHA-256 does not match the archive")
    return Check("sha256_sidecar", True, actual)


def inspect_zip(archive: Path) -> tuple[list[Check], list[zipfile.ZipInfo]]:
    checks: list[Check] = []
    try:
        with zipfile.ZipFile(archive) as bundle:
            infos = bundle.infolist()
            total_size = sum(info.file_size for info in infos)
            oversized_members = [
                info.filename for info in infos if info.file_size > MAX_MEMBER_BYTES
            ]
            excessive_ratios = [
                info.filename
                for info in infos
                if info.file_size > 0
                and info.file_size / max(info.compress_size, 1) > MAX_COMPRESSION_RATIO
            ]
            encrypted = [info.filename for info in infos if info.flag_bits & 0x1]
            reasonable = (
                len(infos) <= MAX_ZIP_ENTRIES
                and total_size <= MAX_UNCOMPRESSED_BYTES
                and not oversized_members
                and not excessive_ratios
                and not encrypted
            )
            checks.append(
                Check(
                    "zip_limits",
                    reasonable,
                    f"entries={len(infos)}, uncompressed_bytes={total_size}, "
                    f"oversized={len(oversized_members)}, "
                    f"excessive_ratio={len(excessive_ratios)}, encrypted={len(encrypted)}",
                )
            )
            names = {_safe_member_path(info.filename) for info in infos}
            safe = None not in names and not any(_is_symlink(info) for info in infos)
            if reasonable:
                bad_member = bundle.testzip()
                checks.append(
                    Check("zip_integrity", bad_member is None, bad_member or "CRC checks passed")
                )
            else:
                checks.append(
                    Check("zip_integrity", False, "CRC scan skipped because ZIP limits failed")
                )
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        return [Check("zip_integrity", False, f"Unreadable ZIP: {exc}")], []

    checks.append(Check("zip_safe_paths", safe, "No absolute, traversal, or symlink entries"))

    safe_paths = [path for path in names if path is not None]
    normalized_names = [
        path.as_posix()
        for info in infos
        if (path := _safe_member_path(info.filename)) is not None
    ]
    duplicates = sorted(name for name, count in Counter(normalized_names).items() if count > 1)
    checks.append(
        Check(
            "zip_unique_paths",
            not duplicates,
            "No duplicate entries" if not duplicates else f"duplicates={duplicates!r}",
        )
    )
    roots = {path.parts[0] for path in safe_paths}
    structure_ok = roots == {ROOT_NAME}
    checks.append(Check("zip_single_root", structure_ok, f"roots={sorted(roots)!r}"))

    relative_names = {
        PurePosixPath(*path.parts[1:]).as_posix()
        for path in safe_paths
        if path.parts and path.parts[0] == ROOT_NAME
    }
    missing = [required for required in REQUIRED_FILES if required not in relative_names]
    sample_notes = [
        name for name in relative_names if name.startswith("Sample Vault/") and name.endswith(".md")
    ]
    if not sample_notes:
        missing.append("Sample Vault/*.md")
    checks.append(
        Check(
            "required_files",
            not missing,
            "All required files present" if not missing else f"missing={missing!r}",
        )
    )

    forbidden = []
    for relative in relative_names:
        path = PurePosixPath(relative)
        lowered = path.name.lower()
        if lowered in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            forbidden.append(relative)
    checks.append(
        Check(
            "forbidden_runtime_files",
            not forbidden,
            "No secrets, databases, or generated skills"
            if not forbidden
            else f"forbidden={sorted(forbidden)!r}",
        )
    )
    return checks, infos


def inspect_dependencies(archive: Path) -> Check:
    member = f"{ROOT_NAME}/dependency-versions.txt"
    manifest_member = f"{ROOT_NAME}/THIRD_PARTY_LICENSES/python-packages/manifest.json"
    try:
        with zipfile.ZipFile(archive) as bundle:
            text = bundle.read(member).decode("utf-8-sig")
            manifest = json.loads(bundle.read(manifest_member).decode("utf-8"))
    except (KeyError, OSError, UnicodeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        return Check("dependency_inventory", False, f"Could not read dependency inventory: {exc}")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    invalid = [line for line in lines if not DEPENDENCY_LINE.fullmatch(line)]
    vcs_or_urls = [
        line
        for line in lines
        if "@" in line
        or "://" in line
        or line.lower().startswith(("-e ", "git+", "file:", "ssh:"))
    ]
    inventory_versions = {
        re.sub(r"[-_.]+", "-", name).lower(): version
        for line in lines
        if DEPENDENCY_LINE.fullmatch(line)
        for name, version in [line.split("==", 1)]
    }
    inventory_names = set(inventory_versions)
    manifest_packages = manifest.get("packages") if isinstance(manifest, dict) else None
    manifest_names: set[str] = set()
    manifest_versions: dict[str, str] = {}
    manifest_invalid = not isinstance(manifest_packages, list)
    license_file_errors: list[str] = []
    allowed_external = {"skill-dna-compiler", "streamlit"}
    if isinstance(manifest_packages, list):
        try:
            with zipfile.ZipFile(archive) as bundle:
                archive_names = set(bundle.namelist())
                for package in manifest_packages:
                    if (
                        not isinstance(package, dict)
                        or not isinstance(package.get("name"), str)
                        or not isinstance(package.get("version"), str)
                        or package.get("status") not in {"collected", "external"}
                        or not isinstance(package.get("files"), list)
                    ):
                        manifest_invalid = True
                        continue
                    package_name = re.sub(r"[-_.]+", "-", package["name"]).lower()
                    status = package["status"]
                    files = package["files"]
                    manifest_names.add(package_name)
                    manifest_versions[package_name] = package["version"]
                    if status == "external":
                        if package_name not in allowed_external or files:
                            manifest_invalid = True
                        continue
                    if not files:
                        manifest_invalid = True
                        continue
                    for item in files:
                        if (
                            not isinstance(item, dict)
                            or not isinstance(item.get("path"), str)
                            or not isinstance(item.get("size"), int)
                            or not isinstance(item.get("sha256"), str)
                            or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
                        ):
                            manifest_invalid = True
                            continue
                        member_name = (
                            f"{ROOT_NAME}/THIRD_PARTY_LICENSES/python-packages/"
                            f"{item['path']}"
                        )
                        if member_name not in archive_names:
                            license_file_errors.append(f"missing:{item['path']}")
                            continue
                        content = bundle.read(member_name)
                        digest_matches = hashlib.sha256(content).hexdigest() == item["sha256"]
                        if len(content) != item["size"] or not digest_matches:
                            license_file_errors.append(f"hash_or_size:{item['path']}")
        except (OSError, zipfile.BadZipFile) as exc:
            license_file_errors.append(f"archive:{exc}")
    manifest_count = manifest.get("package_count") if isinstance(manifest, dict) else None
    if manifest_count != len(manifest_names):
        manifest_invalid = True
    missing_manifest = sorted(inventory_names - manifest_names)
    unexpected_manifest = sorted(manifest_names - inventory_names)
    version_mismatches = sorted(
        name
        for name in inventory_names & manifest_names
        if inventory_versions[name] != manifest_versions.get(name)
    )
    expected_project_version = None
    archive_match = BETA_ARCHIVE_NAME.fullmatch(archive.name)
    if archive_match:
        expected_project_version = f"{archive_match.group(1)}b{archive_match.group(2)}"
    actual_project_version = inventory_versions.get("skill-dna-compiler")
    project_version_mismatch = (
        expected_project_version is not None
        and actual_project_version != expected_project_version
    )
    passed = (
        bool(lines)
        and len(inventory_names) == len(lines)
        and not invalid
        and not vcs_or_urls
        and not manifest_invalid
        and not missing_manifest
        and not unexpected_manifest
        and not version_mismatches
        and not project_version_mismatch
        and not license_file_errors
    )
    detail = f"packages={len(lines)}"
    if invalid or vcs_or_urls:
        detail += f", invalid_or_external={sorted(set(invalid + vcs_or_urls))!r}"
    if manifest_invalid or missing_manifest or unexpected_manifest or version_mismatches:
        detail += (
            f", manifest_invalid={manifest_invalid}, missing_manifest={missing_manifest!r}, "
            f"unexpected_manifest={unexpected_manifest!r}, "
            f"version_mismatches={version_mismatches!r}"
        )
    if project_version_mismatch:
        detail += (
            f", project_version={actual_project_version!r}, "
            f"expected_from_archive={expected_project_version!r}"
        )
    if license_file_errors:
        detail += f", license_file_errors={license_file_errors[:10]!r}"
    return Check("dependency_inventory", passed, detail)


def safe_extract(archive: Path, destination: Path) -> Path:
    destination = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            member = _safe_member_path(info.filename)
            if member is None or _is_symlink(info):
                raise ToolRuntimeError(f"Unsafe ZIP member: {info.filename!r}")
            target = (destination / Path(*member.parts)).resolve()
            if target != destination and destination not in target.parents:
                raise ToolRuntimeError(f"ZIP member escaped destination: {info.filename!r}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
    root = destination / ROOT_NAME
    if not root.is_dir():
        raise ToolRuntimeError("Extracted candidate root is missing")
    return root


def packaged_import_smoke(root: Path, *, timeout: float = 90.0) -> Check:
    executable = root / EXECUTABLE_NAME
    environment = os.environ.copy()
    environment.pop("OPENAI_API_KEY", None)
    environment[SMOKE_ENV] = "1"
    environment["SKILL_DNA_ENVIRONMENT"] = "production"
    try:
        result = subprocess.run(
            [str(executable)],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Check("packaged_import_smoke", False, f"Could not complete smoke test: {exc}")
    output = f"{result.stdout}\n{result.stderr}"
    passed = result.returncode == 0 and SMOKE_MARKER in output
    return Check(
        "packaged_import_smoke",
        passed,
        f"exit_code={result.returncode}, "
        f"marker={'present' if SMOKE_MARKER in output else 'missing'}",
    )


def _parse_endpoint(endpoint: str) -> tuple[str, int] | None:
    endpoint = endpoint.strip()
    if endpoint.startswith("["):
        close = endpoint.rfind("]:")
        if close < 0:
            return None
        host, port_text = endpoint[1:close], endpoint[close + 2 :]
    else:
        host, separator, port_text = endpoint.rpartition(":")
        if not separator:
            return None
    if host == "0.0.0.0":
        host = "0.0.0.0"
    try:
        return host, int(port_text)
    except ValueError:
        return None


def windows_tcp_listeners() -> list[Listener]:
    if os.name != "nt":
        raise ToolRuntimeError("Packaged runtime verification requires Windows")
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ToolRuntimeError(f"Could not inspect TCP listeners: {exc}") from exc
    listeners: list[Listener] = []
    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) < 5 or columns[0].upper() != "TCP" or columns[3].upper() != "LISTENING":
            continue
        parsed = _parse_endpoint(columns[1])
        try:
            pid = int(columns[4])
        except ValueError:
            continue
        if parsed:
            listeners.append(Listener(parsed[0], parsed[1], pid))
    return listeners


def windows_descendant_pids(parent_pid: int) -> set[int]:
    if os.name != "nt":
        raise ToolRuntimeError("Process-tree inspection requires Windows")
    # Toolhelp snapshots work as a standard user.  CIM/WMI process enumeration
    # can be denied on hardened PCs and would make the verifier require elevation.
    import ctypes
    from ctypes import wintypes

    class ProcessEntry32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_snapshot = kernel32.CreateToolhelp32Snapshot
    create_snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    create_snapshot.restype = wintypes.HANDLE
    process_first = kernel32.Process32FirstW
    process_first.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W)]
    process_first.restype = wintypes.BOOL
    process_next = kernel32.Process32NextW
    process_next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W)]
    process_next.restype = wintypes.BOOL

    snapshot = create_snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if snapshot == wintypes.HANDLE(-1).value:
        raise ToolRuntimeError(
            f"Could not inspect the launched process tree (Windows error {ctypes.get_last_error()})"
        )
    rows: list[tuple[int, int]] = []
    try:
        entry = ProcessEntry32W()
        entry.dwSize = ctypes.sizeof(entry)
        success = process_first(snapshot, ctypes.byref(entry))
        while success:
            rows.append((int(entry.th32ProcessID), int(entry.th32ParentProcessID)))
            success = process_next(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)

    children: dict[int, set[int]] = {}
    for pid, parent in rows:
        children.setdefault(parent, set()).add(pid)
    descendants = {parent_pid}
    pending = [parent_pid]
    while pending:
        current = pending.pop()
        for child in children.get(current, set()) - descendants:
            descendants.add(child)
            pending.append(child)
    return descendants


def _http_ok(port: int, path: str, expected_body: str | None = None) -> bool:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read(1024).decode("utf-8", errors="replace")
        return response.status == 200 and (expected_body is None or body.strip() == expected_body)
    except OSError:
        return False
    finally:
        connection.close()


def _stop_owned_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def packaged_runtime_health(
    root: Path,
    *,
    timeout: float = 60.0,
    listener_provider: Callable[[], list[Listener]] = windows_tcp_listeners,
    descendant_provider: Callable[[int], set[int]] = windows_descendant_pids,
) -> list[Check]:
    executable = root / EXECUTABLE_NAME
    environment = os.environ.copy()
    environment.pop("OPENAI_API_KEY", None)
    environment.pop(SMOKE_ENV, None)
    environment[HEADLESS_ENV] = "1"
    environment["SKILL_DNA_ENVIRONMENT"] = "production"
    isolated_runtime = Path(tempfile.mkdtemp(prefix=".verification-runtime-", dir=root))
    environment["SKILL_DNA_DATABASE_PATH"] = str(isolated_runtime / "skill-dna.db")
    # Ensure startup cannot inspect a real Windows Credential Manager entry.
    environment["PYTHON_KEYRING_BACKEND"] = "keyring.backends.null.Keyring"
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    output_log = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
    try:
        try:
            process = subprocess.Popen(
                [str(executable)],
                cwd=root,
                env=environment,
                stdout=output_log,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creationflags,
            )
        except OSError as exc:
            return [Check("packaged_runtime_start", False, f"Could not launch candidate: {exc}")]

        owned_listeners: list[Listener] = []
        healthy: Listener | None = None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and process.poll() is None:
            pids = descendant_provider(process.pid)
            owned_listeners = [listener for listener in listener_provider() if listener.pid in pids]
            loopback = [listener for listener in owned_listeners if listener.host in LOOPBACK_HOSTS]
            for listener in loopback:
                if _http_ok(listener.port, "/") and _http_ok(
                    listener.port, "/_stcore/health", expected_body="ok"
                ):
                    healthy = listener
                    break
            if healthy:
                break
            time.sleep(0.25)
        _stop_owned_process(process)
        output_log.seek(0)
        captured_output = output_log.read()
    except ToolRuntimeError:
        if "process" in locals():
            _stop_owned_process(process)
        raise
    finally:
        output_log.close()

    failure_markers = ("Traceback (most recent call last):", "ModuleNotFoundError:", "ImportError:")
    output_failure = next((marker for marker in failure_markers if marker in captured_output), None)
    started = healthy is not None and output_failure is None
    loopback_only = bool(owned_listeners) and all(
        listener.host in LOOPBACK_HOSTS for listener in owned_listeners
    )
    listeners = [f"{item.host}:{item.port}/pid={item.pid}" for item in owned_listeners]
    return [
        Check(
            "packaged_runtime_health",
            started,
            f"HTTP root and health passed on 127.0.0.1:{healthy.port}"
            if healthy and output_failure is None
            else f"Packaged output contained {output_failure}"
            if output_failure
            else f"No healthy listener before timeout; exit_code={process.returncode}",
        ),
        Check("loopback_only_listener", loopback_only, f"listeners={listeners!r}"),
    ]


def verify_candidate(
    archive: Path,
    *,
    checksum_path: Path | None = None,
    run_runtime: bool = True,
) -> VerificationReport:
    archive = archive.resolve()
    if not archive.is_file():
        raise ToolRuntimeError(f"Candidate archive not found: {archive}")
    checksum_path = (checksum_path or Path(f"{archive}.sha256")).resolve()
    digest = sha256_file(archive)
    checks = [_checksum_check(archive, checksum_path, digest)]
    zip_checks, _ = inspect_zip(archive)
    checks.extend(zip_checks)
    checks.append(inspect_dependencies(archive))

    static_passed = all(check.passed for check in checks)
    if run_runtime and static_passed:
        if os.name != "nt":
            raise ToolRuntimeError("Packaged EXE checks require Windows")
        with tempfile.TemporaryDirectory(prefix="skill-dna-rc-verify-") as temporary:
            root = safe_extract(archive, Path(temporary))
            checks.append(packaged_import_smoke(root))
            if checks[-1].passed:
                checks.extend(packaged_runtime_health(root))
    elif run_runtime:
        checks.append(Check("runtime_checks", False, "Skipped because static checks failed"))

    status = "pass" if checks and all(check.passed for check in checks) else "fail"
    return VerificationReport(
        archive=str(archive),
        archive_sha256=digest,
        generated_at=datetime.now(UTC).isoformat(),
        status=status,
        checks=checks,
    )


def markdown_report(report: VerificationReport) -> str:
    rows = ["| Check | Result | Detail |", "|---|---|---|"]
    for check in report.checks:
        detail = check.detail.replace("|", "\\|").replace("\n", " ")
        rows.append(f"| `{check.name}` | {'PASS' if check.passed else 'FAIL'} | {detail} |")
    return "\n".join(
        [
            "# Windows candidate verification",
            "",
            f"- Status: **{report.status.upper()}**",
            f"- Archive: `{Path(report.archive).name}`",
            f"- SHA-256: `{report.archive_sha256}`",
            f"- Generated: `{report.generated_at}`",
            "",
            *rows,
            "",
        ]
    )


def write_reports(report: VerificationReport, report_dir: Path) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(report.archive).name
    json_path = report_dir / f"{stem}.verification.json"
    markdown_path = report_dir / f"{stem}.verification.md"
    if json_path.exists() or markdown_path.exists():
        raise ToolRuntimeError("Refusing to overwrite an existing verification report")
    json_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    try:
        markdown_path.write_text(markdown_report(report), encoding="utf-8")
    except Exception:
        json_path.unlink(missing_ok=True)
        raise
    return json_path, markdown_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Windows candidate ZIP")
    parser.add_argument("--checksum", type=Path, help="SHA-256 sidecar (defaults to ZIP.sha256)")
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("verification-reports"),
        help="New JSON and Markdown report destination",
    )
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="Skip packaged EXE checks (the report cannot qualify as a full RC pass)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = verify_candidate(
            args.archive,
            checksum_path=args.checksum,
            run_runtime=not args.static_only,
        )
        if args.static_only:
            report.checks.append(Check("runtime_checks", False, "Skipped by --static-only"))
            report.status = "fail"
        json_path, markdown_path = write_reports(report, args.report_dir.resolve())
    except ToolRuntimeError as exc:
        print(f"Verifier runtime error: {exc}", file=sys.stderr)
        _try_write_runtime_error_report(args.archive, args.report_dir, exc)
        return 2
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Verifier runtime error: {exc}", file=sys.stderr)
        _try_write_runtime_error_report(args.archive, args.report_dir, exc)
        return 2
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    return 0 if report.passed else 1


def _try_write_runtime_error_report(archive: Path, report_dir: Path, exc: Exception) -> None:
    """Best-effort error evidence; never masks the original exit code or overwrites files."""
    resolved = archive.resolve()
    try:
        digest = sha256_file(resolved) if resolved.is_file() else ""
        report = VerificationReport(
            archive=str(resolved),
            archive_sha256=digest,
            generated_at=datetime.now(UTC).isoformat(),
            status="error",
            checks=[Check("tool_runtime", False, str(exc))],
        )
        write_reports(report, report_dir.resolve())
    except (OSError, ToolRuntimeError, ValueError):
        pass


if __name__ == "__main__":
    raise SystemExit(main())
