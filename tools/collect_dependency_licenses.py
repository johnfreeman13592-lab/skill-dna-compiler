"""Collect installed package license files for an offline Windows bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from importlib import metadata
from pathlib import Path, PurePosixPath


class LicenseCollectionError(RuntimeError):
    """Dependency license collection could not be completed safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _portable_component(value: str, *, max_length: int) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-") or "license"
    if len(sanitized) <= max_length:
        return sanitized
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"{sanitized[: max_length - len(digest) - 1]}-{digest}"


def _export_relative_path(
    canonical_name: str,
    version: str,
    source_path: PurePosixPath,
    index: int,
) -> Path:
    package_folder = _portable_component(
        f"{canonical_name}-{version}",
        max_length=48,
    )
    source_name = _portable_component(source_path.name, max_length=36)
    return Path(package_folder) / f"{index:03d}-{source_name}"


def parse_inventory(path: Path) -> list[tuple[str, str]]:
    packages: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if "==" not in line:
            raise LicenseCollectionError(
                f"Unsupported dependency inventory line {line_number}: {line!r}"
            )
        name, version = (part.strip() for part in line.split("==", 1))
        canonical = _canonical_name(name)
        if not name or not version or canonical in seen:
            raise LicenseCollectionError(
                f"Invalid or duplicate dependency at line {line_number}: {line!r}"
            )
        seen.add(canonical)
        packages.append((name, version))
    if not packages:
        raise LicenseCollectionError("Dependency inventory is empty")
    return packages


def _is_license_path(path: PurePosixPath) -> bool:
    lowered = [part.lower() for part in path.parts]
    name = lowered[-1]
    has_license_directory = any(
        part in {"license", "licenses", "licence", "licences"} for part in lowered
    )
    return has_license_directory or name.startswith(
        ("license", "licence", "copying", "notice", "copyright")
    )


def _safe_relative(path: PurePosixPath) -> Path:
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise LicenseCollectionError(f"Unsafe installed license path: {path}")
    return Path(*path.parts)


def collect_dependency_licenses(
    inventory_path: Path,
    destination: Path,
    *,
    allow_missing: set[str] | None = None,
) -> dict[str, object]:
    inventory_path = inventory_path.resolve(strict=True)
    destination = destination.resolve(strict=False)
    if destination.exists():
        raise LicenseCollectionError(f"Refusing to overwrite license destination: {destination}")
    allowed = {_canonical_name(name) for name in (allow_missing or set())}
    package_records: list[dict[str, object]] = []
    failures: list[str] = []

    for inventory_name, inventory_version in parse_inventory(inventory_path):
        canonical = _canonical_name(inventory_name)
        try:
            distribution = metadata.distribution(inventory_name)
        except metadata.PackageNotFoundError:
            failures.append(f"{inventory_name}: installed distribution was not found")
            continue
        installed_version = distribution.version
        if installed_version != inventory_version:
            failures.append(
                f"{inventory_name}: inventory={inventory_version}, installed={installed_version}"
            )
            continue

        collected: list[dict[str, object]] = []
        license_paths: list[tuple[PurePosixPath, object]] = []
        for package_path in distribution.files or ():
            pure_path = PurePosixPath(str(package_path).replace("\\", "/"))
            if not _is_license_path(pure_path):
                continue
            _safe_relative(pure_path)
            license_paths.append((pure_path, package_path))

        for index, (pure_path, package_path) in enumerate(
            sorted(license_paths, key=lambda item: item[0].as_posix()),
            1,
        ):
            source = Path(distribution.locate_file(package_path))
            if not source.is_file() or source.is_symlink():
                continue
            target_relative = _export_relative_path(
                canonical,
                inventory_version,
                pure_path,
                index,
            )
            target = destination / target_relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            collected.append(
                {
                    "path": target_relative.as_posix(),
                    "source_path": pure_path.as_posix(),
                    "size": target.stat().st_size,
                    "sha256": _sha256(target),
                }
            )

        if not collected and canonical not in allowed:
            failures.append(f"{inventory_name}: no installed license or notice files found")
        package_records.append(
            {
                "name": canonical,
                "version": inventory_version,
                "status": "collected" if collected else "external",
                "files": collected,
            }
        )

    if failures:
        if destination.exists():
            shutil.rmtree(destination)
        raise LicenseCollectionError("License collection failed:\n- " + "\n- ".join(failures))

    manifest = {
        "schema_version": 1,
        "package_count": len(package_records),
        "packages": package_records,
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--allow-missing", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        manifest = collect_dependency_licenses(
            args.inventory,
            args.destination,
            allow_missing=set(args.allow_missing),
        )
    except (OSError, LicenseCollectionError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"status": "pass", "package_count": manifest["package_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
