from __future__ import annotations

from skill_dna_compiler.domain import WorkflowStep
from skill_dna_compiler.extraction.payloads import ExtractionPayload
from skill_dna_compiler.extraction.schemas import (
    ExtractedCandidate,
    ExtractedSourceReference,
    ExtractionResult,
)

_DEMO_COPY = {
    "en": {
        "fallback_title": "Selected note",
        "name_suffix": " demo candidate",
        "description": "A mock candidate for checking the review UI and citation validation.",
        "trigger": "Checking the extraction UI without network access",
        "do_not_use": "Using this as a real Skill",
        "principle": "Do not treat mock output as AI analysis",
        "workflow": "Review the citation and displayed content",
        "constraint": "Do not approve or export this candidate",
        "reason": "Uses a quote present in the selected document to verify the evidence path",
        "confidence": "Deterministic mock data",
        "warning": "This candidate was not extracted by AI",
    },
    "ja": {
        "fallback_title": "選択メモ",
        "name_suffix": "のデモ候補",
        "description": "候補レビュー画面と引用検証を確認するためのモック候補です。",
        "trigger": "抽出UIをネットワークなしで確認するとき",
        "do_not_use": "実際のSkillとして利用するとき",
        "principle": "モック結果をAI分析結果として扱わない",
        "workflow": "引用と表示を確認する",
        "constraint": "承認・出力しない",
        "reason": "選択文書に存在する引用で検証経路を確認するため",
        "confidence": "固定モックデータのため",
        "warning": "これはAIが抽出した候補ではありません",
    },
    "zh-CN": {
        "fallback_title": "所选笔记",
        "name_suffix": "演示候选",
        "description": "用于检查候选审核界面和引用验证的模拟候选。",
        "trigger": "在无网络环境下检查提取界面时",
        "do_not_use": "作为真实 Skill 使用时",
        "principle": "不要把模拟结果当作 AI 分析结果",
        "workflow": "检查引用和显示内容",
        "constraint": "不要批准或导出此候选",
        "reason": "使用所选文档中确实存在的引用来验证证据路径",
        "confidence": "固定的模拟数据",
        "warning": "此候选并非由 AI 提取",
    },
}


def build_demo_extraction_result(
    payload: ExtractionPayload,
    *,
    language: str = "en",
) -> ExtractionResult:
    """Build one source-valid UI fixture without pretending to perform AI analysis."""

    copy = _DEMO_COPY.get(language, _DEMO_COPY["en"])
    for document in payload.documents:
        quote = next(
            (line.strip() for line in document.content.splitlines() if line.strip()),
            "",
        )
        if not quote:
            continue
        quote = quote[:240]
        title = document.title.strip() or copy["fallback_title"]
        return ExtractionResult(
            candidates=[
                ExtractedCandidate(
                    name=f"{title[:80]}{copy['name_suffix']}",
                    description=copy["description"],
                    category="mock-preview",
                    generality="evaluation-only",
                    triggers=[copy["trigger"]],
                    do_not_use_when=[copy["do_not_use"]],
                    principles=[copy["principle"]],
                    workflow=[WorkflowStep(order=1, action=copy["workflow"])],
                    constraints=[copy["constraint"]],
                    source_references=[
                        ExtractedSourceReference(
                            document_id=document.document_id,
                            quote=quote,
                            reason=copy["reason"],
                        )
                    ],
                    confidence=1.0,
                    confidence_reason=copy["confidence"],
                    warnings=[copy["warning"]],
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
