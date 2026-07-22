from __future__ import annotations

from skill_dna_compiler.domain import WorkflowStep
from skill_dna_compiler.extraction.payloads import ExtractionPayload
from skill_dna_compiler.extraction.schemas import (
    ExtractedCandidate,
    ExtractedSourceReference,
    ExtractionResult,
)


def build_demo_extraction_result(payload: ExtractionPayload) -> ExtractionResult:
    """Build one source-valid UI fixture without pretending to perform AI analysis."""

    for document in payload.documents:
        quote = next(
            (line.strip() for line in document.content.splitlines() if line.strip()),
            "",
        )
        if not quote:
            continue
        quote = quote[:240]
        title = document.title.strip() or "選択メモ"
        return ExtractionResult(
            candidates=[
                ExtractedCandidate(
                    name=f"{title[:80]}のデモ候補",
                    description="候補レビュー画面と引用検証を確認するためのモック候補です。",
                    category="mock-preview",
                    generality="evaluation-only",
                    triggers=["抽出UIをネットワークなしで確認するとき"],
                    do_not_use_when=["実際のSkillとして利用するとき"],
                    principles=["モック結果をAI分析結果として扱わない"],
                    workflow=[WorkflowStep(order=1, action="引用と表示を確認する")],
                    constraints=["承認・出力しない"],
                    source_references=[
                        ExtractedSourceReference(
                            document_id=document.document_id,
                            quote=quote,
                            reason="選択文書に存在する引用で検証経路を確認するため",
                        )
                    ],
                    confidence=1.0,
                    confidence_reason="固定モックデータのため",
                    warnings=["これはAIが抽出した候補ではありません"],
                )
            ]
        )
    return ExtractionResult(candidates=[])


class StaticMockExtractionProvider:
    """Return a validated fixture without network access or API charges."""

    def __init__(self, result: ExtractionResult | None = None) -> None:
        self._result = result or ExtractionResult(candidates=[])
        self.last_payload: ExtractionPayload | None = None

    def extract(self, payload: ExtractionPayload) -> ExtractionResult:
        self.last_payload = payload
        return self._result.model_copy(deep=True)
