from __future__ import annotations

from skill_dna_compiler.extraction.payloads import ExtractionPayload
from skill_dna_compiler.extraction.provider import (
    ExtractionProviderError,
    SkillExtractionProvider,
)
from skill_dna_compiler.extraction.schemas import ExtractionResult
from skill_dna_compiler.extraction.validator import (
    ExtractionValidationError,
    validate_source_quotes,
)
from skill_dna_compiler.storage.repositories import ExtractionRepository


class ExtractionService:
    def __init__(self, repository: ExtractionRepository) -> None:
        self._repository = repository

    def run(
        self,
        *,
        payload: ExtractionPayload,
        provider: SkillExtractionProvider,
        model: str,
        prompt_version: str,
    ) -> ExtractionResult:
        _, result = self.run_with_id(
            payload=payload,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
        )
        return result

    def run_with_id(
        self,
        *,
        payload: ExtractionPayload,
        provider: SkillExtractionProvider,
        model: str,
        prompt_version: str,
    ) -> tuple[str, ExtractionResult]:
        """Run one extraction and return its exact persisted run identity."""

        run_id = self._repository.start_run(model=model, prompt_version=prompt_version)
        try:
            result = provider.extract(payload)
            validate_source_quotes(result, payload)
            self._repository.complete_run(run_id, result)
        except ExtractionProviderError as exc:
            self._repository.fail_run(run_id, safe_message=exc.user_message)
            raise
        except ExtractionValidationError as exc:
            safe_message = "抽出結果の引用を元メモで確認できませんでした。再試行してください。"
            self._repository.fail_run(run_id, safe_message=safe_message)
            raise ExtractionProviderError(safe_message, retryable=True) from exc
        except Exception as exc:
            safe_message = "抽出処理に失敗しました。再試行してください。"
            self._repository.fail_run(run_id, safe_message=safe_message)
            raise ExtractionProviderError(safe_message, retryable=True) from exc

        return run_id, result
