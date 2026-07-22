from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

from tools import verify_windows_candidate as verifier


def _candidate(
    tmp_path: Path,
    *,
    additions: dict[str, bytes] | None = None,
    dependencies: str = "streamlit==1.59.2\nskill-dna-compiler==0.1.0b2\n",
) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    archive = tmp_path / "candidate.zip"
    manifest = {
        "schema_version": 1,
        "package_count": 2,
        "packages": [
            {"name": "streamlit", "version": "1.59.2", "status": "external", "files": []},
            {
                "name": "skill-dna-compiler",
                "version": "0.1.0b2",
                "status": "external",
                "files": [],
            },
        ],
    }
    files = {
        verifier.EXECUTABLE_NAME: b"fake executable",
        "README.txt": b"quick start",
        "_internal/streamlit/static/index.html": b"<!doctype html>",
        "docs/beta-quick-start.md": b"quick start",
        "docs/beta-test-checklist.md": b"checklist",
        "docs/privacy.md": b"privacy",
        "LICENSE": b"MPL-2.0",
        "THIRD_PARTY_NOTICES.md": b"notices",
        "THIRD_PARTY_LICENSES/streamlit-1.59.2/LICENSE": b"Apache-2.0",
        "THIRD_PARTY_LICENSES/streamlit-1.59.2/NOTICES": b"upstream notices",
        "THIRD_PARTY_LICENSES/python-packages/manifest.json": json.dumps(manifest).encode(),
        "dependency-versions.txt": dependencies.encode(),
        "Sample Vault/example.md": b"# Example",
    }
    files.update(additions or {})
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for relative, body in files.items():
            bundle.writestr(f"{verifier.ROOT_NAME}/{relative}", body)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    sidecar = Path(f"{archive}.sha256")
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive, sidecar


def _by_name(checks: list[verifier.Check]) -> dict[str, verifier.Check]:
    return {check.name: check for check in checks}


def test_valid_candidate_passes_checksum_structure_and_dependency_checks(tmp_path: Path):
    archive, sidecar = _candidate(tmp_path)
    digest = verifier.sha256_file(archive)

    checksum = verifier._checksum_check(archive, sidecar, digest)
    structure, _ = verifier.inspect_zip(archive)
    dependencies = verifier.inspect_dependencies(archive)

    assert checksum.passed
    assert all(check.passed for check in structure)
    assert dependencies.passed


def test_tampered_archive_fails_sidecar_checksum(tmp_path: Path):
    archive, sidecar = _candidate(tmp_path)
    with archive.open("ab") as stream:
        stream.write(b"tampered")

    check = verifier._checksum_check(archive, sidecar, verifier.sha256_file(archive))

    assert not check.passed
    assert "does not match" in check.detail


def test_forbidden_runtime_file_and_external_dependency_are_rejected(tmp_path: Path):
    archive, _ = _candidate(
        tmp_path,
        additions={"runtime/skill-dna.db": b"secret"},
        dependencies="streamlit==1.59.2\nproject @ https://example.test/project.zip\n",
    )

    checks, _ = verifier.inspect_zip(archive)
    dependencies = verifier.inspect_dependencies(archive)

    assert not _by_name(checks)["forbidden_runtime_files"].passed
    assert not dependencies.passed
    assert "external" in dependencies.detail


def test_dependency_manifest_must_match_inventory(tmp_path: Path):
    bad_manifest = {
        "schema_version": 1,
        "package_count": 1,
        "packages": [
            {"name": "streamlit", "version": "1.59.2", "status": "external", "files": []}
        ],
    }
    archive, _ = _candidate(
        tmp_path,
        additions={
            "THIRD_PARTY_LICENSES/python-packages/manifest.json": json.dumps(
                bad_manifest
            ).encode()
        },
    )

    check = verifier.inspect_dependencies(archive)

    assert not check.passed
    assert "missing_manifest" in check.detail


def test_dependency_manifest_must_reference_real_matching_license_files(tmp_path: Path):
    bad_manifest = {
        "schema_version": 1,
        "package_count": 2,
        "packages": [
            {
                "name": "streamlit",
                "version": "1.59.2",
                "status": "external",
                "files": [],
            },
            {
                "name": "skill-dna-compiler",
                "version": "0.1.0b2",
                "status": "collected",
                "files": [
                    {"path": "missing/LICENSE", "size": 3, "sha256": "a" * 64}
                ],
            },
        ],
    }
    archive, _ = _candidate(
        tmp_path,
        additions={
            "THIRD_PARTY_LICENSES/python-packages/manifest.json": json.dumps(
                bad_manifest
            ).encode()
        },
    )

    check = verifier.inspect_dependencies(archive)

    assert not check.passed
    assert "license_file_errors" in check.detail


def test_traversal_and_duplicate_members_are_rejected(tmp_path: Path):
    archive, _ = _candidate(tmp_path)
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(archive, "a") as bundle:
            bundle.writestr("../escaped.txt", b"escape")
            bundle.writestr(
                f"{verifier.ROOT_NAME}/docs/privacy.md",
                b"duplicate",
            )

    checks, _ = verifier.inspect_zip(archive)

    assert not _by_name(checks)["zip_safe_paths"].passed
    assert not _by_name(checks)["zip_unique_paths"].passed


def test_corrupt_zip_and_missing_required_file_are_verification_failures(tmp_path: Path):
    corrupt = tmp_path / "corrupt.zip"
    corrupt.write_bytes(b"this is not a zip")
    checksum = Path(f"{corrupt}.sha256")
    checksum.write_text(
        f"{verifier.sha256_file(corrupt)}  {corrupt.name}\n",
        encoding="utf-8",
    )
    missing, _ = _candidate(tmp_path / "missing")
    with zipfile.ZipFile(missing, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(
            f"{verifier.ROOT_NAME}/dependency-versions.txt",
            "streamlit==1.59.2\n",
        )

    corrupt_report = verifier.verify_candidate(corrupt, run_runtime=False)
    missing_checks, _ = verifier.inspect_zip(missing)

    assert corrupt_report.status == "fail"
    assert not _by_name(missing_checks)["required_files"].passed


def test_safe_extract_keeps_files_under_temporary_destination(tmp_path: Path):
    archive, _ = _candidate(tmp_path)
    destination = tmp_path / "extracted"
    destination.mkdir()

    root = verifier.safe_extract(archive, destination)

    assert root == destination / verifier.ROOT_NAME
    assert (root / verifier.EXECUTABLE_NAME).read_bytes() == b"fake executable"
    assert not (tmp_path / "escaped.txt").exists()


class _FakeProcess:
    pid = 8123

    def __init__(self) -> None:
        self.returncode = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


def test_runtime_health_accepts_owned_loopback_listener_and_stops_only_launched_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root = tmp_path / verifier.ROOT_NAME
    root.mkdir()
    (root / verifier.EXECUTABLE_NAME).write_bytes(b"fake")
    process = _FakeProcess()
    launched: dict[str, object] = {}

    def fake_popen(*args, **kwargs):
        launched.update(kwargs)
        return process

    monkeypatch.setattr(verifier.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(verifier, "_http_ok", lambda port, path, expected_body=None: True)

    checks = verifier.packaged_runtime_health(
        root,
        timeout=0.1,
        listener_provider=lambda: [verifier.Listener("127.0.0.1", 43123, process.pid)],
        descendant_provider=lambda parent: {parent},
    )

    assert all(check.passed for check in checks)
    assert process.terminated
    assert not process.killed
    environment = launched["env"]
    assert isinstance(environment, dict)
    database_path = Path(environment["SKILL_DNA_DATABASE_PATH"])
    assert database_path.is_relative_to(root)
    assert database_path.parent.name.startswith(".verification-runtime-")
    assert environment["PYTHON_KEYRING_BACKEND"] == "keyring.backends.null.Keyring"
    assert "OPENAI_API_KEY" not in environment


def test_runtime_health_rejects_non_loopback_listener(tmp_path: Path, monkeypatch):
    root = tmp_path / verifier.ROOT_NAME
    root.mkdir()
    (root / verifier.EXECUTABLE_NAME).write_bytes(b"fake")
    process = _FakeProcess()
    monkeypatch.setattr(verifier.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(verifier, "_http_ok", lambda port, path, expected_body=None: True)

    checks = verifier.packaged_runtime_health(
        root,
        timeout=0.01,
        listener_provider=lambda: [
            verifier.Listener("127.0.0.1", 43123, process.pid),
            verifier.Listener("0.0.0.0", 43124, process.pid),
        ],
        descendant_provider=lambda parent: {parent},
    )

    assert checks[0].passed
    assert not checks[1].passed


def test_import_smoke_and_runtime_start_failures_are_classified_as_failed_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root = tmp_path / verifier.ROOT_NAME
    root.mkdir()
    (root / verifier.EXECUTABLE_NAME).write_bytes(b"fake")
    monkeypatch.setattr(
        verifier.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 3, "", "boom"),
    )

    smoke = verifier.packaged_import_smoke(root)
    monkeypatch.setattr(
        verifier.subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("cannot start")),
    )
    runtime = verifier.packaged_runtime_health(root)

    assert not smoke.passed
    assert "exit_code=3" in smoke.detail
    assert len(runtime) == 1
    assert not runtime[0].passed
    assert "cannot start" in runtime[0].detail


def test_runtime_timeout_is_a_failed_check_and_process_is_stopped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root = tmp_path / verifier.ROOT_NAME
    root.mkdir()
    (root / verifier.EXECUTABLE_NAME).write_bytes(b"fake")
    process = _FakeProcess()
    monkeypatch.setattr(verifier.subprocess, "Popen", lambda *args, **kwargs: process)

    checks = verifier.packaged_runtime_health(
        root,
        timeout=0,
        listener_provider=lambda: [],
        descendant_provider=lambda parent: {parent},
    )

    assert not checks[0].passed
    assert not checks[1].passed
    assert process.terminated


def test_reports_are_machine_readable_and_never_overwritten(tmp_path: Path):
    archive, _ = _candidate(tmp_path)
    report = verifier.VerificationReport(
        archive=str(archive),
        archive_sha256="a" * 64,
        generated_at="2026-07-21T00:00:00+00:00",
        status="pass",
        checks=[verifier.Check("example", True, "ok")],
    )

    json_path, markdown_path = verifier.write_reports(report, tmp_path / "reports")

    assert json.loads(json_path.read_text("utf-8"))["status"] == "pass"
    assert "| `example` | PASS | ok |" in markdown_path.read_text("utf-8")
    with pytest.raises(verifier.ToolRuntimeError, match="overwrite"):
        verifier.write_reports(report, tmp_path / "reports")


def test_cli_exit_codes_distinguish_verification_failure_and_tool_failure(tmp_path: Path):
    archive, _ = _candidate(tmp_path)

    failure = verifier.main(
        [str(archive), "--static-only", "--report-dir", str(tmp_path / "failure-report")]
    )
    tool_failure = verifier.main(
        [str(tmp_path / "missing.zip"), "--report-dir", str(tmp_path / "missing-report")]
    )

    assert failure == 1
    assert tool_failure == 2
    error_report = tmp_path / "missing-report" / "missing.zip.verification.json"
    assert json.loads(error_report.read_text("utf-8"))["status"] == "error"
