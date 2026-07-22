"""Opt-in live Alpha E2E. Never runs unless explicitly enabled."""

import json
import os
import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RUN_LIVE = os.getenv("SKILL_DNA_RUN_LIVE_E2E") == "1"


@pytest.mark.skipif(not RUN_LIVE, reason="live API E2E is opt-in")
def test_selected_obsidian_note_to_exported_skill():
    vault = Path(os.environ["SKILL_DNA_E2E_VAULT"])
    note = os.environ["SKILL_DNA_E2E_NOTE"]
    database = Path(os.environ["SKILL_DNA_DATABASE_PATH"])
    export_root = Path(os.environ["SKILL_DNA_E2E_EXPORT_ROOT"])
    if database.exists():
        with sqlite3.connect(database) as connection:
            existing_candidates = connection.execute(
                "SELECT COUNT(*) FROM skill_candidates"
            ).fetchone()[0]
        if existing_candidates:
            raise AssertionError("Use a fresh E2E database to avoid another API charge")
    if export_root.exists() and any(export_root.iterdir()):
        raise AssertionError("Use an empty E2E export folder")
    export_root.mkdir(parents=True, exist_ok=True)

    app = AppTest.from_file("app.py").run(timeout=60)
    next(widget for widget in app.text_input if widget.label == "Vaultフォルダ").set_value(
        str(vault)
    )
    next(button for button in app.button if button.label == "Vaultを読み込む").click()
    app.run(timeout=60)
    next(
        widget
        for widget in app.multiselect
        if widget.label == "AI分析対象候補（まだ送信されません）"
    ).set_value([note])
    app.run(timeout=60)
    next(button for button in app.button if button.label == "送信内容を準備する").click()
    app.run(timeout=60)

    payload_text = next(code.value for code in app.code if '"documents"' in code.value)
    payload = json.loads(payload_text)
    assert [document["path"] for document in payload["documents"]] == [note]

    next(
        checkbox
        for checkbox in app.checkbox
        if checkbox.label == "伏字済みの送信内容を確認しました"
    ).set_value(True)
    next(
        checkbox
        for checkbox in app.checkbox
        if checkbox.label == "表示された料金目安を確認し、API料金の発生に同意します"
    ).set_value(True)
    app.run(timeout=60)
    next(
        button
        for button in app.button
        if button.label == "OpenAIで実抽出する（API料金が発生します）"
    ).click()
    app.run(timeout=120)

    assert not app.exception
    assert any("OpenAI実抽出が完了" in item.value for item in app.success)
    usage = dict(app.session_state["actual_api_usage"])
    print("ALPHA_E2E_USAGE=" + json.dumps(usage, sort_keys=True))

    next(button for button in app.button if button.label == "承認する").click()
    app.run(timeout=60)
    next(
        checkbox
        for checkbox in app.checkbox
        if checkbox.label == "変換前後を確認し、ローカルDBへ保存します"
    ).set_value(True)
    app.run(timeout=60)
    next(
        button for button in app.button if button.label == "Skill DNAとして保存"
    ).click()
    app.run(timeout=60)

    next(
        widget for widget in app.text_input if widget.label == "出力先の親フォルダ"
    ).set_value(str(export_root))
    app.run(timeout=60)
    next(
        checkbox
        for checkbox in app.checkbox
        if checkbox.label == "出力内容と出力先を確認しました"
    ).set_value(True)
    app.run(timeout=60)
    next(button for button in app.button if button.label == "SKILL.mdを出力").click()
    app.run(timeout=60)

    with sqlite3.connect(database) as connection:
        candidate = connection.execute(
            "SELECT name, status FROM skill_candidates ORDER BY created_at LIMIT 1"
        ).fetchone()
        skill = connection.execute(
            "SELECT name, slug, version FROM skill_dna ORDER BY created_at LIMIT 1"
        ).fetchone()
        exports = connection.execute("SELECT COUNT(*) FROM export_records").fetchone()
    assert candidate is not None and candidate[1] == "approved"
    assert skill is not None and skill[2] == "0.1.0"
    assert exports == (1,)
    exported = export_root / skill[1] / "SKILL.md"
    assert exported.is_file()
    print(
        "ALPHA_E2E_RESULT="
        + json.dumps(
            {
                "candidate_name": candidate[0],
                "skill_name": skill[0],
                "skill_slug": skill[1],
                "skill_version": skill[2],
                "exported_path": str(exported),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
