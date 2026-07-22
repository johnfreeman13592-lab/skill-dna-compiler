from skill_dna_compiler.extraction.schemas import ExtractedCandidate
from skill_dna_compiler.review import find_duplicate_candidates, merge_candidate_data


def _candidate(**updates) -> ExtractedCandidate:
    data = {
        "name": "既存実装を先に確認する",
        "description": "変更前に既存ファイルを調査する。",
        "category": "development",
        "generality": "cross-project",
        "triggers": ["開発を始めるとき"],
        "do_not_use_when": [],
        "principles": ["再利用を優先する"],
        "workflow": [{"order": 1, "action": "既存ファイルを読む"}],
        "constraints": [],
        "source_references": [
            {
                "document_id": "doc_1",
                "quote": "既存ファイルを確認する",
                "reason": "明示的なルール",
            }
        ],
        "confidence": 0.9,
        "confidence_reason": "直接記述されている",
        "warnings": [],
    }
    data.update(updates)
    return ExtractedCandidate.model_validate(data)


def test_duplicate_detection_is_deterministic_and_source_aware():
    first = _candidate()
    second = _candidate(name="既存コードを先に確認する", confidence=0.8)
    unrelated = _candidate(
        name="週次レポートを作成する",
        description="売上指標を毎週集計する。",
        triggers=["週末"],
        principles=["数値を検証する"],
        workflow=[{"order": 1, "action": "CSVを集計する"}],
        source_references=[
            {
                "document_id": "doc_2",
                "quote": "毎週集計する",
                "reason": "報告手順",
            }
        ],
    )

    matches = find_duplicate_candidates(
        [("first", first), ("second", second), ("other", unrelated)]
    )

    assert [(match.left_id, match.right_id) for match in matches] == [
        ("first", "second")
    ]
    assert matches[0].score >= 0.62
    assert "出典文書が重複" in matches[0].reasons


def test_manual_merge_unions_guidance_and_sources_conservatively():
    primary = _candidate()
    secondary = _candidate(
        name="確認してから変更する",
        category="operations",
        triggers=["修正するとき"],
        principles=["再利用を優先する", "影響範囲を確認する"],
        workflow=[{"order": 1, "action": "テストを読む"}],
        source_references=[
            {
                "document_id": "doc_2",
                "quote": "テストを先に確認する",
                "reason": "別の明示的なルール",
            }
        ],
        confidence=0.7,
        confidence_reason="別の直接記述",
    )

    merged = merge_candidate_data(primary, secondary)

    assert merged.name == primary.name
    assert merged.category == primary.category
    assert merged.triggers == ["開発を始めるとき", "修正するとき"]
    assert merged.principles == ["再利用を優先する", "影響範囲を確認する"]
    assert [step.action for step in merged.workflow] == [
        "既存ファイルを読む",
        "テストを読む",
    ]
    assert [reference.document_id for reference in merged.source_references] == [
        "doc_1",
        "doc_2",
    ]
    assert merged.confidence == 0.7
    assert any("手動統合" in warning for warning in merged.warnings)
    assert any("カテゴリが異なる" in warning for warning in merged.warnings)
