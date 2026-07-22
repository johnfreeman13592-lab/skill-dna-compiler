from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from skill_dna_compiler.domain import (
    CandidateStatus,
    InstructionTrace,
    SkillDNA,
    SkillUsageStatus,
    SkillUsefulness,
)
from skill_dna_compiler.extraction.schemas import ExtractedCandidate, ExtractionResult
from skill_dna_compiler.review.traces import (
    reconcile_instruction_traces,
    require_valid_instruction_traces,
    source_reference_fingerprint,
)
from skill_dna_compiler.storage.database import (
    CandidateMergeSourceRecord,
    DocumentRecord,
    ExportRecord,
    ExtractionRunRecord,
    SkillCandidateRecord,
    SkillDNARecord,
    SkillDNAVersionRecord,
    SkillFeedbackRecord,
    SourceReferenceRecord,
    VaultRecord,
)
from skill_dna_compiler.vault import VaultFile


@dataclass(frozen=True)
class SavedVault:
    id: str
    name: str
    root_path: str
    exclude_paths: tuple[str, ...]


@dataclass(frozen=True)
class SavedCandidate:
    id: str
    extraction_run_id: str
    candidate: ExtractedCandidate
    instruction_traces: tuple[InstructionTrace, ...]
    status: CandidateStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class SavedSkillDNAVersion:
    version: str
    skill_dna: SkillDNA
    created_at: datetime


@dataclass(frozen=True)
class SavedExport:
    id: str
    skill_dna_id: str
    destination_path: str
    exported_version: str
    exported_at: datetime


@dataclass(frozen=True)
class SavedSkillFeedback:
    id: str
    skill_dna_id: str
    skill_version: str
    usage_status: SkillUsageStatus
    usefulness: SkillUsefulness
    worked_well: str
    needs_improvement: str
    created_at: datetime


class VaultRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def latest(self) -> SavedVault | None:
        with self._sessions() as session:
            record = session.scalars(
                select(VaultRecord).order_by(VaultRecord.updated_at.desc()).limit(1)
            ).first()
            if record is None:
                return None
            return SavedVault(
                id=record.id,
                name=record.name,
                root_path=record.root_path,
                exclude_paths=tuple(record.exclude_paths),
            )

    def save_scan(
        self, root: Path, exclude_paths: tuple[str, ...], files: list[VaultFile]
    ) -> str:
        resolved_root = str(root.expanduser().resolve(strict=True))
        now = datetime.now(UTC)
        with self._sessions() as session:
            vault = session.scalar(
                select(VaultRecord).where(VaultRecord.root_path == resolved_root)
            )
            if vault is None:
                vault = VaultRecord(
                    id=f"vault_{uuid4().hex}",
                    name=Path(resolved_root).name,
                    root_path=resolved_root,
                    include_paths=[],
                    exclude_paths=list(exclude_paths),
                    created_at=now,
                    updated_at=now,
                )
                session.add(vault)
                session.flush()
            else:
                vault.exclude_paths = list(exclude_paths)
                vault.updated_at = now

            existing = {
                item.relative_path: item
                for item in session.scalars(
                    select(DocumentRecord).where(DocumentRecord.vault_id == vault.id)
                )
            }
            scanned_paths: set[str] = set()
            for file in files:
                scanned_paths.add(file.relative_path)
                document = existing.get(file.relative_path)
                if document is None:
                    document = DocumentRecord(
                        id=f"doc_{uuid4().hex}",
                        vault_id=vault.id,
                        relative_path=file.relative_path,
                        title=file.title,
                        content_hash=file.content_hash,
                        modified_at=file.modified_at,
                        indexed_at=now,
                        status="active",
                    )
                    session.add(document)
                else:
                    document.title = file.title
                    document.content_hash = file.content_hash
                    document.modified_at = file.modified_at
                    document.indexed_at = now
                    document.status = "active"

            for relative_path, document in existing.items():
                if relative_path not in scanned_paths:
                    document.status = "missing"
                    document.indexed_at = now

            session.commit()
            return vault.id

    def document_ids_for_paths(
        self, vault_id: str, relative_paths: list[str]
    ) -> dict[str, str]:
        if not relative_paths:
            return {}
        with self._sessions() as session:
            documents = session.scalars(
                select(DocumentRecord).where(
                    DocumentRecord.vault_id == vault_id,
                    DocumentRecord.relative_path.in_(relative_paths),
                    DocumentRecord.status == "active",
                )
            ).all()
        result = {document.relative_path: document.id for document in documents}
        missing = sorted(set(relative_paths) - result.keys())
        if missing:
            raise ValueError(f"Selected notes are not active in the index: {', '.join(missing)}")
        return result


class ExtractionRepository:
    """Persist extraction state without storing note payloads or API secrets."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def start_run(self, *, model: str, prompt_version: str) -> str:
        run_id = f"run_{uuid4().hex}"
        with self._sessions() as session:
            session.add(
                ExtractionRunRecord(
                    id=run_id,
                    model=model,
                    prompt_version=prompt_version,
                    started_at=datetime.now(UTC),
                    completed_at=None,
                    status="running",
                    error_message=None,
                )
            )
            session.commit()
        return run_id

    def complete_run(self, run_id: str, result: ExtractionResult) -> None:
        now = datetime.now(UTC)
        with self._sessions() as session:
            run = session.get(ExtractionRunRecord, run_id)
            if run is None:
                raise ValueError("Extraction run does not exist")
            if run.status != "running":
                raise ValueError("Extraction run is already finalized")

            for candidate in result.candidates:
                candidate_id = f"candidate_{uuid4().hex}"
                session.add(
                    SkillCandidateRecord(
                        id=candidate_id,
                        extraction_run_id=run_id,
                        name=candidate.name,
                        description=candidate.description,
                        candidate_data=candidate.model_dump(mode="json"),
                        confidence=candidate.confidence,
                        status="pending",
                        created_at=now,
                        updated_at=now,
                    )
                )
                self._add_source_references(session, candidate_id, candidate)
            run.status = "completed"
            run.completed_at = now
            run.error_message = None
            session.commit()

    def list_candidates(
        self, *, status: CandidateStatus | None = None
    ) -> list[SavedCandidate]:
        statement = select(SkillCandidateRecord).order_by(
            SkillCandidateRecord.updated_at.desc()
        )
        if status is not None:
            statement = statement.where(SkillCandidateRecord.status == status.value)
        with self._sessions() as session:
            records = session.scalars(statement).all()
        return [self._saved_candidate(record) for record in records]

    def get_candidate(self, candidate_id: str) -> SavedCandidate:
        with self._sessions() as session:
            record = session.get(SkillCandidateRecord, candidate_id)
            if record is None:
                raise ValueError("Skill candidate does not exist")
            return self._saved_candidate(record)

    def update_candidate(
        self, candidate_id: str, candidate: ExtractedCandidate
    ) -> SavedCandidate:
        with self._sessions() as session:
            record = session.get(SkillCandidateRecord, candidate_id)
            if record is None:
                raise ValueError("Skill candidate does not exist")
            current = self._saved_candidate(record)
            _require_candidate_sources_match_records(session, record, current.candidate)
            if candidate.source_references != current.candidate.source_references:
                raise ValueError("Source references cannot be changed during review")
            record.name = candidate.name
            record.description = candidate.description
            payload = candidate.model_dump(mode="json")
            payload["instruction_traces"] = [
                trace.model_dump(mode="json")
                for trace in reconcile_instruction_traces(
                    candidate, current.instruction_traces
                )
            ]
            record.candidate_data = payload
            record.confidence = candidate.confidence
            record.status = CandidateStatus.PENDING.value
            record.updated_at = datetime.now(UTC)
            session.commit()
            return self._saved_candidate(record)

    def set_candidate_status(
        self, candidate_id: str, status: CandidateStatus
    ) -> SavedCandidate:
        with self._sessions() as session:
            record = session.get(SkillCandidateRecord, candidate_id)
            if record is None:
                raise ValueError("Skill candidate does not exist")
            if status is CandidateStatus.APPROVED:
                saved = self._saved_candidate(record)
                _require_candidate_sources_match_records(session, record, saved.candidate)
                require_valid_instruction_traces(
                    saved.candidate, saved.instruction_traces
                )
            record.status = status.value
            record.updated_at = datetime.now(UTC)
            session.commit()
            return self._saved_candidate(record)

    def save_instruction_trace(
        self, candidate_id: str, trace: InstructionTrace
    ) -> SavedCandidate:
        with self._sessions() as session:
            record = session.get(SkillCandidateRecord, candidate_id)
            if record is None:
                raise ValueError("Skill candidate does not exist")
            saved = self._saved_candidate(record)
            _require_candidate_sources_match_records(session, record, saved.candidate)
            reconciled = reconcile_instruction_traces(
                saved.candidate, saved.instruction_traces
            )
            trace_by_key = {item.instruction_key: item for item in reconciled}
            current = trace_by_key.get(trace.instruction_key)
            if current is None or current.instruction_hash != trace.instruction_hash:
                raise ValueError("The instruction changed; review the current text again")
            known_sources = {
                source_reference_fingerprint(source)
                for source in saved.candidate.source_references
            }
            if set(trace.source_reference_fingerprints) - known_sources:
                raise ValueError("The trace refers to an unknown source reference")
            trace_by_key[trace.instruction_key] = trace
            ordered = [trace_by_key[item.instruction_key] for item in reconciled]
            payload = saved.candidate.model_dump(mode="json")
            payload["instruction_traces"] = [
                item.model_dump(mode="json") for item in ordered
            ]
            record.candidate_data = payload
            record.status = CandidateStatus.PENDING.value
            record.updated_at = datetime.now(UTC)
            session.commit()
            return self._saved_candidate(record)

    def create_merged_candidate(
        self,
        primary_id: str,
        secondary_id: str,
        merged: ExtractedCandidate,
    ) -> SavedCandidate:
        if primary_id == secondary_id:
            raise ValueError("A candidate cannot be merged with itself")
        now = datetime.now(UTC)
        with self._sessions() as session:
            primary = session.get(SkillCandidateRecord, primary_id)
            secondary = session.get(SkillCandidateRecord, secondary_id)
            if primary is None or secondary is None:
                raise ValueError("Both source candidates must exist")
            if CandidateStatus.REJECTED.value in {primary.status, secondary.status}:
                raise ValueError("Rejected candidates cannot be merged")

            lineage = session.scalars(
                select(CandidateMergeSourceRecord).where(
                    CandidateMergeSourceRecord.source_candidate_id.in_(
                        [primary_id, secondary_id]
                    )
                )
            ).all()
            merged_counts = Counter(item.merged_candidate_id for item in lineage)
            if any(count >= 2 for count in merged_counts.values()):
                raise ValueError("These candidates have already been merged")

            primary_data = self._saved_candidate(primary).candidate
            secondary_data = self._saved_candidate(secondary).candidate
            expected_sources = {
                (source.document_id, source.quote, source.reason)
                for source in [
                    *primary_data.source_references,
                    *secondary_data.source_references,
                ]
            }
            actual_sources = {
                (source.document_id, source.quote, source.reason)
                for source in merged.source_references
            }
            if actual_sources != expected_sources:
                raise ValueError("Merged candidate must preserve all validated sources")

            merged_id = f"candidate_{uuid4().hex}"
            record = SkillCandidateRecord(
                id=merged_id,
                extraction_run_id=primary.extraction_run_id,
                name=merged.name,
                description=merged.description,
                candidate_data=merged.model_dump(mode="json"),
                confidence=merged.confidence,
                status=CandidateStatus.PENDING.value,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            session.flush([record])
            self._add_source_references(session, merged_id, merged)
            for source_id in (primary_id, secondary_id):
                session.add(
                    CandidateMergeSourceRecord(
                        id=f"merge_source_{uuid4().hex}",
                        merged_candidate_id=merged_id,
                        source_candidate_id=source_id,
                        created_at=now,
                    )
                )
            primary.status = CandidateStatus.ON_HOLD.value
            primary.updated_at = now
            secondary.status = CandidateStatus.ON_HOLD.value
            secondary.updated_at = now
            session.commit()
            return self._saved_candidate(record)

    def fail_run(self, run_id: str, *, safe_message: str) -> None:
        with self._sessions() as session:
            run = session.get(ExtractionRunRecord, run_id)
            if run is None:
                raise ValueError("Extraction run does not exist")
            if run.status != "running":
                raise ValueError("Extraction run is already finalized")
            run.status = "failed"
            run.completed_at = datetime.now(UTC)
            run.error_message = safe_message
            session.commit()

    @staticmethod
    def _saved_candidate(record: SkillCandidateRecord) -> SavedCandidate:
        payload = dict(record.candidate_data)
        traces = tuple(
            InstructionTrace.model_validate(item)
            for item in payload.pop("instruction_traces", [])
        )
        return SavedCandidate(
            id=record.id,
            extraction_run_id=record.extraction_run_id,
            candidate=ExtractedCandidate.model_validate(payload),
            instruction_traces=traces,
            status=CandidateStatus(record.status),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _add_source_references(
        session: Session,
        candidate_id: str,
        candidate: ExtractedCandidate,
    ) -> None:
        for reference in candidate.source_references:
            session.add(
                SourceReferenceRecord(
                    id=f"source_{uuid4().hex}",
                    candidate_id=candidate_id,
                    document_id=reference.document_id,
                    excerpt=reference.quote,
                    heading=None,
                    start_line=None,
                    end_line=None,
                    reason=reference.reason,
                )
            )


def _require_skill_matches_candidate(
    skill_dna: SkillDNA, saved_candidate: SavedCandidate
) -> None:
    candidate = saved_candidate.candidate
    fields_match = all(
        getattr(skill_dna, field) == getattr(candidate, field)
        for field in (
            "name",
            "description",
            "triggers",
            "do_not_use_when",
            "principles",
            "workflow",
            "constraints",
        )
    )
    skill_sources = [
        source_reference_fingerprint(source) for source in skill_dna.sources
    ]
    candidate_sources = [
        source_reference_fingerprint(source) for source in candidate.source_references
    ]
    skill_traces = [trace.model_dump(mode="json") for trace in skill_dna.instruction_traces]
    candidate_traces = [
        trace.model_dump(mode="json") for trace in saved_candidate.instruction_traces
    ]
    if (
        not fields_match
        or skill_sources != candidate_sources
        or skill_traces != candidate_traces
    ):
        raise ValueError("Skill DNA is older than or differs from the approved candidate")


class SkillDNARepository:
    """Persist the current Skill DNA JSON plus immutable version snapshots."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def list_all(self) -> list[SkillDNA]:
        with self._sessions() as session:
            records = session.scalars(
                select(SkillDNARecord).order_by(SkillDNARecord.updated_at.desc())
            ).all()
        return [SkillDNA.model_validate(record.skill_data) for record in records]

    def get_by_candidate(self, candidate_id: str) -> SkillDNA | None:
        with self._sessions() as session:
            record = session.scalar(
                select(SkillDNARecord).where(SkillDNARecord.candidate_id == candidate_id)
            )
        return None if record is None else SkillDNA.model_validate(record.skill_data)

    def slug_exists(self, slug: str) -> bool:
        with self._sessions() as session:
            return session.scalar(
                select(SkillDNARecord.id).where(SkillDNARecord.slug == slug)
            ) is not None

    def save_version(self, skill_dna: SkillDNA) -> SkillDNA:
        require_valid_instruction_traces(skill_dna)
        now = datetime.now(UTC)
        stored = skill_dna.model_copy(update={"updated_at": now})
        payload = stored.model_dump(mode="json")
        with self._sessions() as session:
            candidate = session.get(SkillCandidateRecord, stored.candidate_id)
            if candidate is None or candidate.status != CandidateStatus.APPROVED.value:
                raise ValueError("Only an approved candidate can become Skill DNA")
            saved_candidate = ExtractionRepository._saved_candidate(candidate)
            _require_candidate_sources_match_records(
                session, candidate, saved_candidate.candidate
            )
            require_valid_instruction_traces(
                saved_candidate.candidate, saved_candidate.instruction_traces
            )
            _require_skill_matches_candidate(stored, saved_candidate)
            record = session.scalar(
                select(SkillDNARecord).where(
                    SkillDNARecord.candidate_id == stored.candidate_id
                )
            )
            if record is None:
                record = SkillDNARecord(
                    id=stored.id,
                    candidate_id=stored.candidate_id,
                    slug=stored.slug,
                    name=stored.name,
                    version=stored.version,
                    skill_data=payload,
                    status=stored.status.value,
                    created_at=stored.created_at,
                    updated_at=now,
                )
                session.add(record)
            else:
                record.slug = stored.slug
                record.name = stored.name
                record.version = stored.version
                record.skill_data = payload
                record.status = stored.status.value
                record.updated_at = now
            session.add(
                SkillDNAVersionRecord(
                    id=f"skill_version_{uuid4().hex}",
                    skill_dna_id=stored.id,
                    version=stored.version,
                    skill_data=payload,
                    created_at=now,
                )
            )
            session.commit()
        return stored

    def list_versions(self, skill_dna_id: str) -> list[SavedSkillDNAVersion]:
        with self._sessions() as session:
            records = session.scalars(
                select(SkillDNAVersionRecord)
                .where(SkillDNAVersionRecord.skill_dna_id == skill_dna_id)
                .order_by(SkillDNAVersionRecord.created_at.asc())
            ).all()
        return [
            SavedSkillDNAVersion(
                version=record.version,
                skill_dna=SkillDNA.model_validate(record.skill_data),
                created_at=record.created_at,
            )
            for record in records
        ]


def _require_persisted_skill_consistency(
    session: Session, record: SkillDNARecord, skill_dna: SkillDNA
) -> None:
    payload = skill_dna.model_dump(mode="json")
    normalized_fields_match = (
        record.id == skill_dna.id
        and record.candidate_id == skill_dna.candidate_id
        and record.slug == skill_dna.slug
        and record.name == skill_dna.name
        and record.version == skill_dna.version
        and record.status == skill_dna.status.value
        and _utc_naive(record.created_at) == _utc_naive(skill_dna.created_at)
        and _utc_naive(record.updated_at) == _utc_naive(skill_dna.updated_at)
    )
    if record.skill_data != payload or not normalized_fields_match:
        raise ValueError("Skill DNA does not match its saved normalized record")
    snapshot = session.scalar(
        select(SkillDNAVersionRecord).where(
            SkillDNAVersionRecord.skill_dna_id == record.id,
            SkillDNAVersionRecord.version == record.version,
        )
    )
    if snapshot is None or snapshot.skill_data != record.skill_data:
        raise ValueError("Skill DNA does not match its immutable version snapshot")


def _require_candidate_sources_match_records(
    session: Session,
    record: SkillCandidateRecord,
    candidate: ExtractedCandidate,
) -> None:
    persisted_sources = session.scalars(
        select(SourceReferenceRecord).where(
            SourceReferenceRecord.candidate_id == record.id
        )
    ).all()
    json_sources = Counter(
        (source.document_id, source.quote, source.reason)
        for source in candidate.source_references
    )
    normalized_sources = Counter(
        (source.document_id, source.excerpt, source.reason)
        for source in persisted_sources
    )
    if json_sources != normalized_sources:
        raise ValueError("Candidate sources do not match their validated source records")


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


class ExportRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def assert_exportable(self, skill_dna: SkillDNA) -> None:
        require_valid_instruction_traces(skill_dna)
        with self._sessions() as session:
            record = session.get(SkillDNARecord, skill_dna.id)
            if record is None:
                raise ValueError("Skill DNA does not exist")
            _require_persisted_skill_consistency(session, record, skill_dna)
            candidate = session.get(SkillCandidateRecord, skill_dna.candidate_id)
            if candidate is None or candidate.status != CandidateStatus.APPROVED.value:
                raise ValueError("The source candidate is no longer approved")
            saved_candidate = ExtractionRepository._saved_candidate(candidate)
            _require_candidate_sources_match_records(
                session, candidate, saved_candidate.candidate
            )
            require_valid_instruction_traces(
                saved_candidate.candidate, saved_candidate.instruction_traces
            )
            _require_skill_matches_candidate(skill_dna, saved_candidate)

    def record_export(self, skill_dna: SkillDNA, *, destination_path: Path) -> SavedExport:
        self.assert_exportable(skill_dna)
        resolved = destination_path.expanduser().resolve(strict=True)
        now = datetime.now(UTC)
        record = ExportRecord(
            id=f"export_{uuid4().hex}",
            skill_dna_id=skill_dna.id,
            target="codex",
            destination_path=str(resolved),
            exported_version=skill_dna.version,
            exported_at=now,
        )
        with self._sessions() as session:
            if session.get(SkillDNARecord, skill_dna.id) is None:
                raise ValueError("Skill DNA does not exist")
            session.add(record)
            session.commit()
        return self._saved_export(record)

    def list_for_skill(self, skill_dna_id: str) -> list[SavedExport]:
        with self._sessions() as session:
            records = session.scalars(
                select(ExportRecord)
                .where(ExportRecord.skill_dna_id == skill_dna_id)
                .order_by(ExportRecord.exported_at.asc())
            ).all()
        return [self._saved_export(record) for record in records]

    @staticmethod
    def _saved_export(record: ExportRecord) -> SavedExport:
        return SavedExport(
            id=record.id,
            skill_dna_id=record.skill_dna_id,
            destination_path=record.destination_path,
            exported_version=record.exported_version,
            exported_at=record.exported_at,
        )


class SkillFeedbackRepository:
    """Store user-entered, local-only feedback without changing a Skill automatically."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def add(
        self,
        skill_dna: SkillDNA,
        *,
        usage_status: SkillUsageStatus,
        usefulness: SkillUsefulness,
        worked_well: str = "",
        needs_improvement: str = "",
    ) -> SavedSkillFeedback:
        worked_well = worked_well.strip()
        needs_improvement = needs_improvement.strip()
        if len(worked_well) > 2_000 or len(needs_improvement) > 2_000:
            raise ValueError("Feedback text must be 2,000 characters or fewer")
        now = datetime.now(UTC)
        record = SkillFeedbackRecord(
            id=f"feedback_{uuid4().hex}",
            skill_dna_id=skill_dna.id,
            skill_version=skill_dna.version,
            usage_status=usage_status.value,
            usefulness=usefulness.value,
            worked_well=worked_well,
            needs_improvement=needs_improvement,
            created_at=now,
        )
        with self._sessions() as session:
            if session.get(SkillDNARecord, skill_dna.id) is None:
                raise ValueError("Skill DNA does not exist")
            session.add(record)
            session.commit()
        return self._saved(record)

    def list_for_skill(self, skill_dna_id: str) -> list[SavedSkillFeedback]:
        with self._sessions() as session:
            records = session.scalars(
                select(SkillFeedbackRecord)
                .where(SkillFeedbackRecord.skill_dna_id == skill_dna_id)
                .order_by(SkillFeedbackRecord.created_at.asc())
            ).all()
        return [self._saved(record) for record in records]

    @staticmethod
    def _saved(record: SkillFeedbackRecord) -> SavedSkillFeedback:
        return SavedSkillFeedback(
            id=record.id,
            skill_dna_id=record.skill_dna_id,
            skill_version=record.skill_version,
            usage_status=SkillUsageStatus(record.usage_status),
            usefulness=SkillUsefulness(record.usefulness),
            worked_well=record.worked_well,
            needs_improvement=record.needs_improvement,
            created_at=record.created_at,
        )
