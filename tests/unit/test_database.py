import sqlite3
from contextlib import closing

import pytest
from sqlalchemy import create_engine, inspect, text

from skill_dna_compiler.storage.database import (
    CURRENT_SCHEMA_VERSION,
    Base,
    Database,
    DatabaseVersionError,
    SchemaMigrationRecord,
)


def test_initialize_creates_expected_tables(tmp_path):
    database = Database(tmp_path / "nested" / "test.db")

    database.initialize()

    assert database.path.exists()
    assert database.engine is not None
    assert set(inspect(database.engine).get_table_names()) == {
        "candidate_merge_sources",
        "documents",
        "export_records",
        "extraction_runs",
        "skill_candidates",
        "skill_dna",
        "skill_dna_versions",
        "skill_feedback",
        "source_references",
        "schema_migrations",
        "vaults",
    }
    with database.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert connection.execute(text("PRAGMA user_version")).scalar_one() == 3
    assert database.schema_version == CURRENT_SCHEMA_VERSION
    assert database.session_factory is not None
    with database.session_factory() as session:
        migration = session.get(SchemaMigrationRecord, 1)
        assert migration is not None
        assert migration.description == "Initial versioned local schema"
        migration_v2 = session.get(SchemaMigrationRecord, 2)
        assert migration_v2 is not None
        assert migration_v2.description == "Add immutable Skill DNA version history"
        migration_v3 = session.get(SchemaMigrationRecord, 3)
        assert migration_v3 is not None
        assert migration_v3.description == "Add local Skill usage feedback history"


def test_v1_database_is_backed_up_and_migrated_to_v2(tmp_path):
    database_path = tmp_path / "v1.db"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE skill_dna_versions"))
        connection.execute(text("DELETE FROM schema_migrations"))
        connection.execute(
            text(
                "INSERT INTO schema_migrations(version, description, applied_at) "
                "VALUES (1, 'Initial versioned local schema', CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(text("PRAGMA user_version=1"))
    engine.dispose()

    database = Database(database_path)
    database.initialize()

    assert database.schema_version == 3
    assert "skill_dna_versions" in inspect(database.engine).get_table_names()
    backups = database.backups.list_backups()
    assert len(backups) == 1
    assert "before-schema-v2" in backups[0].path.name


def test_v2_database_is_backed_up_and_migrated_to_v3(tmp_path):
    database_path = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE skill_feedback"))
        connection.execute(text("DELETE FROM schema_migrations"))
        connection.execute(
            text(
                "INSERT INTO schema_migrations(version, description, applied_at) "
                "VALUES (1, 'Initial versioned local schema', CURRENT_TIMESTAMP), "
                "(2, 'Add immutable Skill DNA version history', CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(text("PRAGMA user_version=2"))
    engine.dispose()

    database = Database(database_path)
    database.initialize()

    assert database.schema_version == 3
    assert "skill_feedback" in inspect(database.engine).get_table_names()
    backups = database.backups.list_backups()
    assert len(backups) == 1
    assert "before-schema-v3" in backups[0].path.name


def test_failed_v2_to_v3_migration_restores_data_and_can_retry(tmp_path, monkeypatch):
    database_path = tmp_path / "v2-with-data.db"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE skill_feedback"))
        connection.execute(text("DELETE FROM schema_migrations WHERE version = 3"))
        connection.execute(text("CREATE TABLE preserved_value (value TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO preserved_value VALUES ('keep-me')"))
        connection.execute(text("PRAGMA user_version=2"))
    engine.dispose()

    database = Database(database_path)
    real_migrate = database._migrate_to_v3

    def migrate_then_fail():
        real_migrate()
        raise RuntimeError("synthetic migration interruption")

    monkeypatch.setattr(database, "_migrate_to_v3", migrate_then_fail)
    with pytest.raises(RuntimeError, match="synthetic migration interruption"):
        database.initialize()

    with closing(sqlite3.connect(database_path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (2,)
        assert connection.execute("SELECT value FROM preserved_value").fetchone() == (
            "keep-me",
        )
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "skill_feedback" not in tables

    retried = Database(database_path)
    retried.initialize()
    assert retried.schema_version == CURRENT_SCHEMA_VERSION
    assert retried.engine is not None
    with retried.engine.connect() as connection:
        assert connection.execute(text("SELECT value FROM preserved_value")).scalar_one() == (
            "keep-me"
        )


def test_legacy_database_is_backed_up_before_v1_migration(tmp_path):
    database_path = tmp_path / "legacy.db"
    legacy_engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(legacy_engine)
    with legacy_engine.begin() as connection:
        connection.execute(text("DROP TABLE candidate_merge_sources"))
        connection.execute(text("DROP TABLE schema_migrations"))
        connection.execute(text("PRAGMA user_version=0"))
        connection.execute(text("CREATE TABLE legacy_data (value TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO legacy_data VALUES ('preserved')"))
    legacy_engine.dispose()

    database = Database(database_path)
    database.initialize()

    backups = database.backups.list_backups()
    assert len(backups) == 1
    assert "before-schema-v1" in backups[0].path.name
    assert backups[0].schema_version == 0
    assert "vaults" in backups[0].tables
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT value FROM legacy_data")).scalar_one() == (
            "preserved"
        )


def test_failed_legacy_migration_restores_original_database(tmp_path):
    database_path = tmp_path / "broken-legacy.db"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("CREATE TABLE vaults (id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO vaults VALUES ('original')")
        connection.commit()

    database = Database(database_path)
    with pytest.raises(DatabaseVersionError, match="missing columns"):
        database.initialize()

    with closing(sqlite3.connect(database_path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (0,)
        assert connection.execute("SELECT id FROM vaults").fetchone() == ("original",)
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "schema_migrations" not in tables


def test_newer_database_version_is_rejected_without_changes(tmp_path):
    database_path = tmp_path / "future.db"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION + 1}")

    database = Database(database_path)
    with pytest.raises(DatabaseVersionError, match="newer"):
        database.initialize()
    assert database.engine is None

    with closing(sqlite3.connect(database_path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (
            CURRENT_SCHEMA_VERSION + 1,
        )


def test_database_restore_creates_safety_backup_and_reinitializes(tmp_path):
    database = Database(tmp_path / "app.db")
    database.initialize()
    assert database.engine is not None
    with database.engine.begin() as connection:
        connection.execute(text("CREATE TABLE local_value (value TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO local_value VALUES ('before')"))
    selected = database.create_backup(reason="known-good")
    with database.engine.begin() as connection:
        connection.execute(text("UPDATE local_value SET value='after'"))

    safety = database.restore_backup(selected.path)

    assert "before-restore" in safety.path.name
    assert database.engine is not None
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT value FROM local_value")).scalar_one() == "before"
    assert len(database.backups.list_backups()) == 2


def test_database_restore_reinstates_current_data_when_reinitialize_fails(
    tmp_path, monkeypatch
):
    database = Database(tmp_path / "app.db")
    database.initialize()
    assert database.engine is not None
    with database.engine.begin() as connection:
        connection.execute(text("CREATE TABLE local_value (value TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO local_value VALUES ('selected-backup')"))
    selected = database.create_backup(reason="selected")
    with database.engine.begin() as connection:
        connection.execute(text("UPDATE local_value SET value='current-data'"))

    real_initialize = database.initialize
    initialize_calls = 0

    def fail_first_reinitialize():
        nonlocal initialize_calls
        initialize_calls += 1
        if initialize_calls == 1:
            raise RuntimeError("synthetic post-restore startup failure")
        real_initialize()

    monkeypatch.setattr(database, "initialize", fail_first_reinitialize)

    with pytest.raises(RuntimeError, match="synthetic post-restore"):
        database.restore_backup(selected.path)

    assert initialize_calls == 2
    assert database.engine is not None
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT value FROM local_value")).scalar_one() == (
            "current-data"
        )
    assert any(
        "before-restore" in backup.path.name
        for backup in database.backups.list_backups()
    )


def test_restore_rolls_back_valid_but_incomplete_application_backup(tmp_path):
    database = Database(tmp_path / "app.db")
    database.initialize()
    assert database.engine is not None
    with database.engine.begin() as connection:
        connection.execute(text("CREATE TABLE local_value (value TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO local_value VALUES ('preserved-current')"))

    database.backups.backup_directory.mkdir()
    incomplete = database.backups.backup_directory / "incomplete.sqlite3"
    with closing(sqlite3.connect(incomplete)) as connection:
        for table in sorted({"vaults", "documents", "extraction_runs", "skill_candidates"}):
            connection.execute(f"CREATE TABLE {table} (id TEXT PRIMARY KEY)")
        connection.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION}")
        connection.commit()

    with pytest.raises(DatabaseVersionError, match="incomplete"):
        database.restore_backup(incomplete)

    assert database.engine is not None
    assert database.schema_version == CURRENT_SCHEMA_VERSION
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT value FROM local_value")).scalar_one() == (
            "preserved-current"
        )


def test_restore_reports_backup_created_by_newer_application(tmp_path):
    database = Database(tmp_path / "app.db")
    database.initialize()
    database.backups.backup_directory.mkdir()
    future = database.backups.backup_directory / "future.sqlite3"
    with closing(sqlite3.connect(future)) as connection:
        for table in sorted({"vaults", "documents", "extraction_runs", "skill_candidates"}):
            connection.execute(f"CREATE TABLE {table} (id TEXT PRIMARY KEY)")
        connection.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION + 1}")
        connection.commit()

    with pytest.raises(DatabaseVersionError, match="newer application version"):
        database.restore_backup(future)


def test_database_restore_rejects_non_application_sqlite_backup(tmp_path):
    database = Database(tmp_path / "app.db")
    database.initialize()
    database.backups.backup_directory.mkdir()
    foreign_backup = database.backups.backup_directory / "foreign.sqlite3"
    with closing(sqlite3.connect(foreign_backup)) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")
        connection.commit()

    with pytest.raises(ValueError, match="not a compatible Skill DNA database"):
        database.restore_backup(foreign_backup)
