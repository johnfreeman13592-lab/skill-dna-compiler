from __future__ import annotations

from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VaultFile(BaseModel):
    model_config = ConfigDict(frozen=True)

    absolute_path: Path
    relative_path: str
    title: str
    size_bytes: int = Field(ge=0)
    modified_at: datetime
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("relative_path")
    @classmethod
    def path_must_be_vault_relative(cls, value: str) -> str:
        path = PurePosixPath(value.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".md":
            raise ValueError("relative_path must be a Markdown file inside the Vault")
        return path.as_posix()


class DocumentSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    heading: str
    level: int = Field(ge=1, le=6)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    content: str


class InternalLink(BaseModel):
    model_config = ConfigDict(frozen=True)

    raw: str
    target: str = Field(min_length=1)
    heading: str | None = None
    alias: str | None = None
    line: int = Field(ge=1)


class ParsedNote(BaseModel):
    model_config = ConfigDict(frozen=True)

    file: VaultFile
    source_text: str
    frontmatter: dict[str, Any]
    body: str
    sections: list[DocumentSection]
    internal_links: list[InternalLink]
