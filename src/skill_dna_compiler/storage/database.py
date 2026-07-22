from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    URL,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from skill_dna_compiler.storage.backups import BackupInfo, SQLiteBackupService

CURRENT_SCHEMA_VERSION = 3
CORE_APPLICATION_TABLES = frozenset(
    {"vaults", "documents", "extraction_runs", "skill_candidates"}
)


class DatabaseVersionError(RuntimeError):
    pass


class Base(DeclarativeBase):
    pass


class SchemaMigrationRecord(Base):
    __tablename__ = "schema_migrations"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(Text)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VaultRecord(Base):
    __tablename__ = "vaults"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    root_path: Mapped[str] = mapped_column(Text)
    include_paths: Mapped[list[str]] = mapped_column(JSON, default=list)
    exclude_paths: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DocumentRecord(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("vault_id", "relative_path"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    vault_id: Mapped[str] = mapped_column(ForeignKey("vaults.id"), index=True)
    relative_path: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(128), index=True)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="active")


class ExtractionRunRecord(Base):
    __tablename__ = "extraction_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))
    error_message: Mapped[str | None] = mapped_column(Text)


class SkillCandidateRecord(Base):
    __tablename__ = "skill_candidates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    extraction_run_id: Mapped[str] = mapped_column(ForeignKey("extraction_runs.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    candidate_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourceReferenceRecord(Base):
    __tablename__ = "source_references"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("skill_candidates.id"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    excerpt: Mapped[str] = mapped_column(Text)
    heading: Mapped[str | None] = mapped_column(Text)
    start_line: Mapped[int | None]
    end_line: Mapped[int | None]
    reason: Mapped[str] = mapped_column(Text)


class CandidateMergeSourceRecord(Base):
    __tablename__ = "candidate_merge_sources"
    __table_args__ = (UniqueConstraint("merged_candidate_id", "source_candidate_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merged_candidate_id: Mapped[str] = mapped_column(
        ForeignKey("skill_candidates.id"), index=True
    )
    source_candidate_id: Mapped[str] = mapped_column(
        ForeignKey("skill_candidates.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SkillDNARecord(Base):
    __tablename__ = "skill_dna"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("skill_candidates.id"), index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(32))
    skill_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SkillDNAVersionRecord(Base):
    __tablename__ = "skill_dna_versions"
    __table_args__ = (UniqueConstraint("skill_dna_id", "version"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    skill_dna_id: Mapped[str] = mapped_column(ForeignKey("skill_dna.id"), index=True)
    version: Mapped[str] = mapped_column(String(32))
    skill_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExportRecord(Base):
    __tablename__ = "export_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    skill_dna_id: Mapped[str] = mapped_column(ForeignKey("skill_dna.id"), index=True)
    target: Mapped[str] = mapped_column(String(64))
    destination_path: Mapped[str] = mapped_column(Text)
    exported_version: Mapped[str] = mapped_column(String(32))
    exported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SkillFeedbackRecord(Base):
    __tablename__ = "skill_feedback"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    skill_dna_id: Mapped[str] = mapped_column(ForeignKey("skill_dna.id"), index=True)
    skill_version: Mapped[str] = mapped_column(String(32))
    usage_status: Mapped[str] = mapped_column(String(32))
    usefulness: Mapped[str] = mapped_column(String(32))
    worked_well: Mapped[str] = mapped_column(Text, default="")
    needs_improvement: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Database:
    """Own the local SQLite engine and schema lifecycle."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self.backups = SQLiteBackupService(self.path)
        self.engine: Engine | None = None
        self.session_factory: sessionmaker[Any] | None = None

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        database_had_data = self.path.is_file() and self.path.stat().st_size > 0
        if self.engine is not None:
            self.engine.dispose()
        url = URL.create("sqlite", database=str(self.path))
        self.engine = create_engine(url, connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", _enable_sqlite_foreign_keys)
        migration_backup: BackupInfo | None = None
        try:
            version = self._read_schema_version()
            if version > CURRENT_SCHEMA_VERSION:
                raise DatabaseVersionError(
                    "The database was created by a newer Skill DNA Compiler version"
                )
            if version < CURRENT_SCHEMA_VERSION:
                existing_tables = set(inspect(self.engine).get_table_names())
                if database_had_data and existing_tables:
                    migration_backup = self.backups.create_backup(
                        reason=f"before-schema-v{version + 1}"
                    )
                if version < 1:
                    self._migrate_to_v1()
                if version < 2:
                    self._migrate_to_v2()
                if version < 3:
                    self._migrate_to_v3()
            self._validate_current_schema()
        except Exception:
            self.engine.dispose()
            self.engine = None
            self.session_factory = None
            if migration_backup is not None:
                self.backups.restore_backup(migration_backup.path)
            raise
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    @property
    def schema_version(self) -> int:
        if self.engine is None:
            raise RuntimeError("Database is not initialized")
        return self._read_schema_version()

    def create_backup(self, *, reason: str = "manual") -> BackupInfo:
        if self.engine is None:
            raise RuntimeError("Database is not initialized")
        return self.backups.create_backup(reason=reason)

    def restore_backup(self, path: Path) -> BackupInfo:
        if self.engine is None:
            raise RuntimeError("Database is not initialized")
        selected = self.backups.inspect_backup(path)
        if not selected.integrity_ok or not CORE_APPLICATION_TABLES.issubset(
            selected.tables
        ):
            raise ValueError("The selected backup is not a compatible Skill DNA database")
        if selected.schema_version > CURRENT_SCHEMA_VERSION:
            raise DatabaseVersionError(
                "The selected backup was created by a newer application version"
            )
        safety_backup = self.create_backup(reason="before-restore")
        self.engine.dispose()
        self.engine = None
        self.session_factory = None
        try:
            self.backups.restore_backup(selected.path)
            self.initialize()
        except Exception:
            self.backups.restore_backup(safety_backup.path)
            self.initialize()
            raise
        return safety_backup

    @staticmethod
    def backup_is_compatible(backup: BackupInfo) -> bool:
        return (
            backup.integrity_ok
            and backup.schema_version <= CURRENT_SCHEMA_VERSION
            and CORE_APPLICATION_TABLES.issubset(backup.tables)
        )

    def _read_schema_version(self) -> int:
        assert self.engine is not None
        with self.engine.connect() as connection:
            return int(connection.exec_driver_sql("PRAGMA user_version").scalar_one())

    def _migrate_to_v1(self) -> None:
        assert self.engine is not None
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            existing = connection.exec_driver_sql(
                "SELECT version FROM schema_migrations WHERE version = 1"
            ).first()
            if existing is None:
                connection.execute(
                    SchemaMigrationRecord.__table__.insert().values(
                        version=1,
                        description="Initial versioned local schema",
                        applied_at=datetime.now(UTC),
                    )
                )
            connection.exec_driver_sql("PRAGMA user_version = 1")

    def _migrate_to_v2(self) -> None:
        assert self.engine is not None
        SkillDNAVersionRecord.__table__.create(self.engine, checkfirst=True)
        with self.engine.begin() as connection:
            existing = connection.exec_driver_sql(
                "SELECT version FROM schema_migrations WHERE version = 2"
            ).first()
            if existing is None:
                connection.execute(
                    SchemaMigrationRecord.__table__.insert().values(
                        version=2,
                        description="Add immutable Skill DNA version history",
                        applied_at=datetime.now(UTC),
                    )
                )
            connection.exec_driver_sql("PRAGMA user_version = 2")

    def _migrate_to_v3(self) -> None:
        assert self.engine is not None
        SkillFeedbackRecord.__table__.create(self.engine, checkfirst=True)
        with self.engine.begin() as connection:
            existing = connection.exec_driver_sql(
                "SELECT version FROM schema_migrations WHERE version = 3"
            ).first()
            if existing is None:
                connection.execute(
                    SchemaMigrationRecord.__table__.insert().values(
                        version=3,
                        description="Add local Skill usage feedback history",
                        applied_at=datetime.now(UTC),
                    )
                )
            connection.exec_driver_sql("PRAGMA user_version = 3")

    def _validate_current_schema(self) -> None:
        assert self.engine is not None
        expected = set(Base.metadata.tables)
        actual = set(inspect(self.engine).get_table_names())
        missing = sorted(expected - actual)
        if missing:
            raise DatabaseVersionError(
                f"Database schema v{CURRENT_SCHEMA_VERSION} is incomplete: "
                f"{', '.join(missing)}"
            )
        inspector = inspect(self.engine)
        column_errors: list[str] = []
        for table_name, table in Base.metadata.tables.items():
            actual_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            missing_columns = sorted(set(table.columns.keys()) - actual_columns)
            if missing_columns:
                column_errors.append(f"{table_name}: {', '.join(missing_columns)}")
        if column_errors:
            raise DatabaseVersionError(
                f"Database schema v{CURRENT_SCHEMA_VERSION} has missing columns: "
                f"{'; '.join(column_errors)}"
            )


def _enable_sqlite_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:
    del connection_record
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
