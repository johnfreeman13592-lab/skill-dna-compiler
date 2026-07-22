import sqlite3
from contextlib import closing

import pytest

from skill_dna_compiler.storage.backups import SQLiteBackupService


def test_backup_is_valid_and_can_restore_previous_data(tmp_path):
    database_path = tmp_path / "app.db"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("CREATE TABLE example (value TEXT NOT NULL)")
        connection.execute("INSERT INTO example VALUES ('before')")
        connection.execute("PRAGMA user_version=3")
        connection.commit()
    service = SQLiteBackupService(database_path)

    backup = service.create_backup(reason="manual-test")
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("UPDATE example SET value='after'")
        connection.commit()
    restored = service.restore_backup(backup.path)

    assert backup.integrity_ok is True
    assert backup.schema_version == 3
    assert backup.tables == ("example",)
    assert restored.path == backup.path
    with closing(sqlite3.connect(database_path)) as connection:
        assert connection.execute("SELECT value FROM example").fetchone() == ("before",)
    assert service.list_backups()[0].path == backup.path


def test_restore_rejects_files_outside_backup_directory(tmp_path):
    database_path = tmp_path / "app.db"
    outside = tmp_path / "outside.sqlite3"
    with closing(sqlite3.connect(database_path)):
        pass
    with closing(sqlite3.connect(outside)):
        pass
    service = SQLiteBackupService(database_path)

    with pytest.raises(ValueError, match="inside the application backup directory"):
        service.restore_backup(outside)


def test_restore_rejects_corrupt_backup(tmp_path):
    database_path = tmp_path / "app.db"
    with closing(sqlite3.connect(database_path)):
        pass
    service = SQLiteBackupService(database_path)
    service.backup_directory.mkdir()
    corrupt = service.backup_directory / "corrupt.sqlite3"
    corrupt.write_bytes(b"not a sqlite database")

    with pytest.raises(ValueError, match="integrity validation"):
        service.restore_backup(corrupt)


def test_list_backups_marks_corrupt_backup_without_hiding_valid_backup(tmp_path):
    database_path = tmp_path / "app.db"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("CREATE TABLE example (value TEXT NOT NULL)")
        connection.execute("PRAGMA user_version=3")
        connection.commit()
    service = SQLiteBackupService(database_path)
    valid = service.create_backup(reason="valid")
    corrupt = service.backup_directory / "corrupt.sqlite3"
    corrupt.write_bytes(b"not a sqlite database")

    backups = service.list_backups()

    assert {item.path for item in backups} == {valid.path, corrupt.resolve()}
    corrupt_info = next(item for item in backups if item.path == corrupt.resolve())
    assert corrupt_info.integrity_ok is False
    assert corrupt_info.inspection_error == "SQLite inspection could not be completed"
    assert service.list_issues == ()


def test_list_backups_skips_one_uninspectable_file_without_hiding_valid_backup(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "app.db"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("CREATE TABLE example (value TEXT NOT NULL)")
        connection.commit()
    service = SQLiteBackupService(database_path)
    valid = service.create_backup(reason="valid")
    unreadable = service.backup_directory / "unreadable.sqlite3"
    unreadable.write_bytes(b"placeholder")
    inspect_backup = service.inspect_backup

    def fail_one_inspection(path):
        if path == unreadable:
            raise PermissionError("simulated access denial")
        return inspect_backup(path)

    monkeypatch.setattr(service, "inspect_backup", fail_one_inspection)

    assert [item.path for item in service.list_backups()] == [valid.path]
    assert len(service.list_issues) == 1
    assert service.list_issues[0].path == unreadable
    assert service.list_issues[0].message == (
        "Permission was denied while inspecting the backup"
    )
