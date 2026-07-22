from __future__ import annotations

from typing import Protocol

from skill_dna_compiler.extraction.payloads import ExtractionPayload
from skill_dna_compiler.extraction.schemas import ExtractionResult


class ExtractionProviderError(RuntimeError):
    """A provider failure safe to surface without leaking request content."""

    def __init__(self, user_message: str, *, retryable: bool) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.retryable = retryable


class SkillExtractionProvider(Protocol):
    def extract(self, payload: ExtractionPayload) -> ExtractionResult: ...
