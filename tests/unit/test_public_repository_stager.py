from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import stage_public_repository as stager


def _minimal_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = tmp_path / "private-project"
    project.mkdir()
    (project / "README.md").write_text("# Public\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "privacy.md").write_text("# Privacy\n", encoding="utf-8")
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    egg_info = project / "src" / "private_project.egg-info"
    egg_info.mkdir()
    (egg_info / "PKG-INFO").write_text("generated\n", encoding="utf-8")
    (project / "tests").mkdir()
    (project / "tests" / "test_secret.py").write_text(
        'SYNTHETIC = "sk-proj-exampleSecretValue1234567890"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(stager, "ROOT_FILES", ("README.md",))
    monkeypatch.setattr(stager, "PUBLIC_DOCS", ("privacy.md",))
    monkeypatch.setattr(stager, "PUBLIC_TREES", ("src", "tests"))
    monkeypatch.setattr(
        stager,
        "SYNTHETIC_CREDENTIAL_FILES",
        {"tests/test_secret.py"},
    )
    return project


def test_stage_public_repository_copies_only_allowlisted_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _minimal_project(tmp_path, monkeypatch)
    (project / "DEVELOPMENT_NOTES.md").write_text("private", encoding="utf-8")
    destination = project / "build" / "public"
    report_path = project / "build" / "public.audit.json"

    report = stager.stage_public_repository(project, destination, report_path)

    assert report["status"] == "pass"
    assert report["history_included"] is False
    assert report["file_count"] == 4
    assert (destination / "README.md").is_file()
    assert (destination / "tests" / "test_secret.py").is_file()
    assert not (destination / "DEVELOPMENT_NOTES.md").exists()
    assert not (destination / "src" / "private_project.egg-info").exists()
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert [item["path"] for item in saved["files"]] == [
        "README.md",
        "docs/privacy.md",
        "src/app.py",
        "tests/test_secret.py",
    ]


def test_private_marker_fails_before_destination_is_created(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _minimal_project(tmp_path, monkeypatch)
    (project / "src" / "app.py").write_text("owner = 'Ryoki'\n", encoding="utf-8")
    destination = project / "build" / "public"

    with pytest.raises(stager.PublicStagingError, match="private marker"):
        stager.stage_public_repository(
            project,
            destination,
            project / "build" / "public.audit.json",
        )

    assert not destination.exists()


def test_existing_destination_is_not_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _minimal_project(tmp_path, monkeypatch)
    destination = project / "build" / "public"
    destination.mkdir(parents=True)

    with pytest.raises(stager.PublicStagingError, match="Refusing to overwrite"):
        stager.stage_public_repository(
            project,
            destination,
            project / "build" / "public.audit.json",
        )


def test_destination_and_report_must_stay_in_private_project_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _minimal_project(tmp_path, monkeypatch)

    with pytest.raises(stager.PublicStagingError, match="project build path"):
        stager.stage_public_repository(
            project,
            tmp_path / "outside-public",
            project / "build" / "public.audit.json",
        )

    with pytest.raises(stager.PublicStagingError, match="project build path"):
        stager.stage_public_repository(
            project,
            project / "build" / "public",
            tmp_path / "outside.audit.json",
        )

    with pytest.raises(stager.PublicStagingError, match="outside the staged public tree"):
        stager.stage_public_repository(
            project,
            project / "build" / "public",
            project / "build" / "public" / "audit.json",
        )


def test_unreviewed_test_credential_fixture_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _minimal_project(tmp_path, monkeypatch)
    (project / "tests" / "unreviewed.py").write_text(
        'SECRET = "ghp_abcdefghijklmnopqrstuvwxyz123456"\n',
        encoding="utf-8",
    )

    with pytest.raises(stager.PublicStagingError, match="reviewed synthetic fixtures"):
        stager.stage_public_repository(
            project,
            project / "build" / "public",
            project / "build" / "public.audit.json",
        )
