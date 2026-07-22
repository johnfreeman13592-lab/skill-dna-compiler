from __future__ import annotations

import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    created_at: datetime
    size_bytes: int
    schema_version: int
    integrity_ok: bool
    tables: tuple[str, ...]
    inspection_error: str | None = None


@dataclass(frozen=True)
class BackupInspectionIssue:
    """A backup candidate that could not be safely inspected."""

    path: Path
    message: str


class SQLiteBackupService:
    """Create and restore validated SQLite backups beside the application DB."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.expanduser().resolve()
        self.backup_directory = self.database_path.parent / (
            f"{self.database_path.name}.backups"
        )
        self._list_issues: tuple[BackupInspectionIssue, ...] = ()

    @property
    def list_issues(self) -> tuple[BackupInspectionIssue, ...]:
        """Problems from the most recent listing, without changing any files."""

        return self._list_issues

    def create_backup(self, *, reason: str) -> BackupInfo:
        if not self.database_path.is_file():
            raise ValueError("The database does not exist yet")
        self.backup_directory.mkdir(parents=True, exist_ok=True)
        reason_slug = re.sub(r"[^a-z0-9]+", "-", reason.casefold()).strip("-")
        reason_slug = reason_slug[:40] or "manual"
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        destination = self.backup_directory / (
            f"{self.database_path.stem}-{timestamp}-{reason_slug}.sqlite3"
        )
        try:
            with closing(sqlite3.connect(self.database_path)) as source:
                with closing(sqlite3.connect(destination)) as target:
                    source.backup(target)
            info = self.inspect_backup(destination)
            if not info.integrity_ok:
                raise ValueError("The created backup failed SQLite integrity validation")
            return info
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    def list_backups(self) -> list[BackupInfo]:
        if not self.backup_directory.is_dir():
            self._list_issues = ()
            return []
        backups: list[BackupInfo] = []
        issues: list[BackupInspectionIssue] = []
        try:
            candidates = list(self.backup_directory.glob("*.sqlite3"))
        except OSError as exc:
            self._list_issues = (
                BackupInspectionIssue(
                    path=self.backup_directory,
                    message=self._inspection_error_message(exc),
                ),
            )
            return []
        for path in candidates:
            try:
                if path.is_file():
                    backups.append(self.inspect_backup(path))
            except (OSError, ValueError) as exc:
                issues.append(
                    BackupInspectionIssue(
                        path=path,
                        message=self._inspection_error_message(exc),
                    )
                )
        self._list_issues = tuple(issues)
        return sorted(backups, key=lambda item: item.created_at, reverse=True)

    def inspect_backup(self, path: Path) -> BackupInfo:
        resolved = self._resolve_backup_path(path)
        integrity_ok = False
        schema_version = 0
        tables: tuple[str, ...] = ()
        inspection_error: str | None = None
        try:
            with closing(
                sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
            ) as connection:
                integrity_ok = connection.execute("PRAGMA quick_check").fetchone() == ("ok",)
                schema_version = int(
                    connection.execute("PRAGMA user_version").fetchone()[0]
                )
                tables = tuple(
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                    )
                )
        except (OSError, sqlite3.Error):
            integrity_ok = False
            schema_version = 0
            tables = ()
            inspection_error = "SQLite inspection could not be completed"
        stat = resolved.stat()
        return BackupInfo(
            path=resolved,
            created_at=datetime.fromtimestamp(stat.st_mtime, UTC),
            size_bytes=stat.st_size,
            schema_version=schema_version,
            integrity_ok=integrity_ok,
            tables=tables,
            inspection_error=inspection_error,
        )

    def restore_backup(self, path: Path) -> BackupInfo:
        source_path = self._resolve_backup_path(path)
        source_info = self.inspect_backup(source_path)
        if not source_info.integrity_ok:
            raise ValueError("The selected backup failed SQLite integrity validation")

        temporary = self.database_path.parent / (
            f".{self.database_path.name}.restore-{uuid4().hex}.tmp"
        )
        try:
            with closing(
                sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)
            ) as source:
                with closing(sqlite3.connect(temporary)) as target:
                    source.backup(target)
                    if target.execute("PRAGMA quick_check").fetchone() != ("ok",):
                        raise ValueError("The restored database failed SQLite integrity validation")
            os.replace(temporary, self.database_path)
        finally:
            temporary.unlink(missing_ok=True)
        return source_info

    def _resolve_backup_path(self, path: Path) -> Path:
        resolved = path.expanduser().resolve(strict=True)
        backup_root = self.backup_directory.resolve()
        if not resolved.is_relative_to(backup_root) or resolved.suffix != ".sqlite3":
            raise ValueError("Backup path must stay inside the application backup directory")
        return resolved

    @staticmethod
    def _inspection_error_message(exc: OSError | ValueError) -> str:
        if isinstance(exc, FileNotFoundError):
            return "The backup disappeared during inspection"
        if isinstance(exc, PermissionError):
            return "Permission was denied while inspecting the backup"
        if isinstance(exc, ValueError):
            return "The backup path was not an allowed local backup path"
        return "The operating system prevented backup inspection"
