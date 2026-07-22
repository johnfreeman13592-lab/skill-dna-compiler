from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from skill_dna_compiler.security import SensitiveDataFinding, SensitiveDataScanner
from skill_dna_compiler.vault import ParsedNote


class PayloadLimitError(ValueError):
    """Raised before transmission when the exact serialized payload is too large."""


class PayloadDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str
    title: str
    path: str
    content_hash: str
    content: str


class ExtractionPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    documents: list[PayloadDocument] = Field(min_length=1)
    redaction_count: int = Field(ge=0)


@dataclass(frozen=True)
class DocumentFinding:
    document_path: str
    location: str
    finding: SensitiveDataFinding


@dataclass(frozen=True)
class PreparedPayload:
    payload: ExtractionPayload
    serialized_json: str
    character_count: int
    findings: tuple[DocumentFinding, ...]


def prepare_extraction_payload(
    notes: list[ParsedNote],
    *,
    max_characters: int,
    max_documents: int = 20,
    scanner: SensitiveDataScanner | None = None,
    document_ids_by_path: Mapping[str, str] | None = None,
) -> PreparedPayload:
    if not notes:
        raise ValueError("At least one selected note is required")
    if len(notes) > max_documents:
        raise PayloadLimitError(f"Select at most {max_documents} notes per extraction")
    if max_characters < 1:
        raise ValueError("max_characters must be positive")

    active_scanner = scanner or SensitiveDataScanner()
    documents: list[PayloadDocument] = []
    all_findings: list[DocumentFinding] = []
    seen_paths: set[str] = set()

    for note in notes:
        path = note.file.relative_path
        if path in seen_paths:
            raise ValueError(f"Duplicate selected note: {path}")
        seen_paths.add(path)
        if document_ids_by_path is None:
            document_id = f"doc_{note.file.content_hash[:16]}"
        else:
            document_id = document_ids_by_path.get(path, "")
            if not document_id:
                raise ValueError(f"Selected note is not indexed in SQLite: {path}")
        path_scan = active_scanner.scan(path)
        title_scan = active_scanner.scan(note.file.title)
        content_scan = active_scanner.scan(note.source_text)
        for location, scan in (
            ("path", path_scan),
            ("title", title_scan),
            ("content", content_scan),
        ):
            all_findings.extend(
                DocumentFinding(document_path=path, location=location, finding=finding)
                for finding in scan.findings
            )
        documents.append(
            PayloadDocument(
                document_id=document_id,
                title=title_scan.sanitized_text,
                path=path_scan.sanitized_text,
                content_hash=note.file.content_hash,
                content=content_scan.sanitized_text,
            )
        )

    payload = ExtractionPayload(documents=documents, redaction_count=len(all_findings))
    serialized = payload.model_dump_json(indent=2)
    character_count = len(serialized)
    if character_count > max_characters:
        raise PayloadLimitError(
            f"Prepared payload has {character_count} characters; limit is {max_characters}"
        )
    return PreparedPayload(
        payload=payload,
        serialized_json=serialized,
        character_count=character_count,
        findings=tuple(all_findings),
    )
