from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

import pytest

from tools import collect_dependency_licenses as collector


class _Distribution:
    def __init__(self, root: Path, version: str, files: list[str]) -> None:
        self.root = root
        self.version = version
        self.files = [PurePosixPath(value) for value in files]

    def locate_file(self, path: PurePosixPath) -> Path:
        return self.root / Path(*path.parts)


def test_collects_license_files_and_records_allowed_external_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed = tmp_path / "installed"
    license_path = installed / "demo-1.0.dist-info" / "licenses" / "LICENSE"
    license_path.parent.mkdir(parents=True)
    license_path.write_text("MIT\n", encoding="utf-8")
    distributions = {
        "demo": _Distribution(installed, "1.0", ["demo-1.0.dist-info/licenses/LICENSE"]),
        "external": _Distribution(installed, "2.0", []),
    }
    monkeypatch.setattr(
        collector.metadata,
        "distribution",
        lambda name: distributions[name],
    )
    inventory = tmp_path / "dependencies.txt"
    inventory.write_text("demo==1.0\nexternal==2.0\n", encoding="utf-8")
    destination = tmp_path / "licenses"

    manifest = collector.collect_dependency_licenses(
        inventory,
        destination,
        allow_missing={"external"},
    )

    assert manifest["package_count"] == 2
    assert [item["status"] for item in manifest["packages"]] == [
        "collected",
        "external",
    ]
    copied = destination / "demo-1.0" / "001-LICENSE"
    assert copied.read_text(encoding="utf-8") == "MIT\n"
    assert manifest["packages"][0]["files"][0]["source_path"] == (
        "demo-1.0.dist-info/licenses/LICENSE"
    )
    saved = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert saved["packages"] == manifest["packages"]


def test_flattens_long_installed_paths_to_a_portable_export_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed = tmp_path / "installed"
    relative = PurePosixPath(
        "very-long-package-name.dist-info/licenses/"
        + "nested/" * 20
        + "A very long dependency license filename that must be shortened.txt"
    )
    license_path = installed / "LICENSE"
    license_path.parent.mkdir(parents=True)
    license_path.write_text("license\n", encoding="utf-8")
    distribution = _Distribution(installed, "2026.7.22", [relative.as_posix()])
    distribution.locate_file = lambda _path: license_path  # type: ignore[method-assign]
    monkeypatch.setattr(collector.metadata, "distribution", lambda _name: distribution)
    inventory = tmp_path / "dependencies.txt"
    inventory.write_text(
        "very-long-package-name-with-an-equally-long-canonical-identifier==2026.7.22\n",
        encoding="utf-8",
    )
    destination = tmp_path / "licenses"

    manifest = collector.collect_dependency_licenses(inventory, destination)

    exported = manifest["packages"][0]["files"][0]
    assert len(exported["path"]) <= 89
    assert exported["source_path"] == relative.as_posix()
    assert (destination / Path(exported["path"])).read_text(encoding="utf-8") == "license\n"


def test_missing_license_and_version_mismatch_fail_without_partial_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed = tmp_path / "installed"
    installed.mkdir()
    distributions = {
        "missing": _Distribution(installed, "1.0", []),
        "mismatch": _Distribution(installed, "2.0", []),
    }
    monkeypatch.setattr(
        collector.metadata,
        "distribution",
        lambda name: distributions[name],
    )
    inventory = tmp_path / "dependencies.txt"
    inventory.write_text("missing==1.0\nmismatch==1.0\n", encoding="utf-8")
    destination = tmp_path / "licenses"

    with pytest.raises(collector.LicenseCollectionError, match="License collection failed"):
        collector.collect_dependency_licenses(inventory, destination)

    assert not destination.exists()


def test_refuses_existing_destination_and_unsupported_inventory(tmp_path: Path) -> None:
    inventory = tmp_path / "dependencies.txt"
    inventory.write_text("demo @ https://example.test/demo.whl\n", encoding="utf-8")
    destination = tmp_path / "licenses"
    destination.mkdir()

    with pytest.raises(collector.LicenseCollectionError, match="overwrite"):
        collector.collect_dependency_licenses(inventory, destination)

    destination.rmdir()
    with pytest.raises(collector.LicenseCollectionError, match="Unsupported"):
        collector.collect_dependency_licenses(inventory, destination)
