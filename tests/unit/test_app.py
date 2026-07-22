import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from skill_dna_compiler import __release_label__
from skill_dna_compiler.config.settings import get_settings

PROJECT_ROOT = Path(__file__).parents[2]


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_app_renders_phase_two_vault_controls(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "app.db"))

    app = AppTest.from_file("app.py").run(timeout=30)

    assert not app.exception
    assert any(
        "sdc-product-title" in item.value and "Skill DNA" in item.value
        for item in app.markdown
    )
    assert any(__release_label__ in item.value for item in app.markdown)
    assert any(item.label == "詳しい5ステップを見る" for item in app.expander)
    assert any("はじめての最短ルート" in item.value for item in app.markdown)
    assert any(widget.label == "Vaultフォルダ" for widget in app.text_input)
    assert any(button.label == "Vaultを読み込む" for button in app.button)
    assert not next(button for button in app.button if "Vault" in button.label).disabled
    assert any(button.label == "今すぐDBバックアップを作成" for button in app.button)
    assert any("OpenAI APIキー設定" in item.value for item in app.subheader)
    workflow_headings = [
        item.value
        for item in app.subheader
        if item.value.startswith(("1.", "3.", "4.", "5."))
    ]
    assert workflow_headings == [
        "1. Obsidianメモを選ぶ",
        "3. Skill候補をレビューする",
        "4. 承認済み候補をSkill DNA化する",
        "5. Codex Skillを出力する",
    ]


def test_app_starts_in_clean_temporary_environment_without_api_key(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "clean-app.db"
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(database_path))

    app = AppTest.from_file(str(PROJECT_ROOT / "app.py")).run(timeout=30)

    assert not app.exception
    assert database_path.is_file()
    assert any("OPENAI_API_KEY" in message.value for message in app.warning)
    assert any("表示できるSkill候補はまだありません" in item.value for item in app.info)
    assert any("出力できるSkill DNAはまだありません" in item.value for item in app.info)
    assert not list(tmp_path.rglob("SKILL.md"))


def test_production_app_saves_and_deletes_key_via_keyring(tmp_path, monkeypatch):
    stored: dict[tuple[str, str], str] = {}
    test_key = "sk-proj-ui-test-never-log"
    database_path = tmp_path / "beta.db"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SKILL_DNA_ENVIRONMENT", "production")
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(database_path))
    monkeypatch.setattr(
        "skill_dna_compiler.credentials.keyring.get_password",
        lambda service, account: stored.get((service, account)),
    )
    monkeypatch.setattr(
        "skill_dna_compiler.credentials.keyring.set_password",
        lambda service, account, value: stored.__setitem__((service, account), value),
    )
    monkeypatch.setattr(
        "skill_dna_compiler.credentials.keyring.delete_password",
        lambda service, account: stored.pop((service, account)),
    )
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py")).run(timeout=30)

    save_button = next(
        button
        for button in app.button
        if button.label == "Windows資格情報ストアへ保存"
    )
    assert not save_button.disabled

    key_input = next(widget for widget in app.text_input if widget.label == "OpenAI APIキー")
    key_input.set_value(test_key)
    app.run(timeout=30)
    next(
        button
        for button in app.button
        if button.label == "Windows資格情報ストアへ保存"
    ).click()
    app.run(timeout=30)

    assert not app.exception
    assert stored
    assert test_key.encode() not in database_path.read_bytes()
    assert any("API通信は行っていません" in item.value for item in app.success)
    assert next(
        widget for widget in app.text_input if widget.label == "OpenAI APIキー"
    ).value == ""

    next(
        checkbox
        for checkbox in app.checkbox
        if checkbox.label == "保存済みAPIキーを削除することを確認しました"
    ).set_value(True)
    app.run(timeout=30)
    next(
        button
        for button in app.button
        if button.label == "Windows資格情報ストアから削除"
    ).click()
    app.run(timeout=30)

    assert not app.exception
    assert not stored
    assert any("保存済みAPIキーを削除しました" in item.value for item in app.success)


def test_app_reports_missing_vault_in_clean_temporary_environment(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "clean-app.db"))
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py")).run(timeout=30)

    missing_vault = tmp_path / "missing-vault"
    next(widget for widget in app.text_input if widget.label == "Vaultフォルダ").set_value(
        str(missing_vault)
    )
    app.run(timeout=30)
    next(button for button in app.button if button.label == "Vaultを読み込む").click()
    app.run(timeout=30)

    assert not app.exception
    assert any("Vault does not exist" in message.value for message in app.error)
    assert not missing_vault.exists()


def test_app_creates_validated_manual_database_backup(tmp_path, monkeypatch):
    database_path = tmp_path / "app.db"
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(database_path))
    app = AppTest.from_file("app.py").run(timeout=30)

    next(
        button for button in app.button if button.label == "今すぐDBバックアップを作成"
    ).click()
    app.run(timeout=30)

    backup_directory = tmp_path / "app.db.backups"
    backups = list(backup_directory.glob("*.sqlite3"))
    assert not app.exception
    assert len(backups) == 1
    assert any("検証済みバックアップ" in message.value for message in app.success)
    restore_button = next(
        button for button in app.button if button.label == "選択したDBバックアップを復元"
    )
    assert restore_button.disabled is True


def test_app_lists_corrupt_backup_without_offering_it_for_restore(tmp_path, monkeypatch):
    database_path = tmp_path / "app.db"
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(database_path))
    app = AppTest.from_file("app.py").run(timeout=30)
    next(
        button for button in app.button if button.label == "今すぐDBバックアップを作成"
    ).click()
    app.run(timeout=30)
    backup_directory = tmp_path / "app.db.backups"
    corrupt = backup_directory / "corrupt.sqlite3"
    corrupt.write_bytes(b"not a sqlite database")

    app.run(timeout=30)

    assert not app.exception
    restore_select = next(
        widget for widget in app.selectbox if widget.label == "復元するバックアップ"
    )
    assert len(restore_select.options) == 1
    assert "corrupt.sqlite3" not in restore_select.options
    assert any("破損または読取不能" in str(table.value) for table in app.dataframe)
    assert corrupt.is_file()


def test_app_skips_permission_denied_backup_without_deleting_it(tmp_path, monkeypatch):
    from skill_dna_compiler.storage.backups import SQLiteBackupService

    database_path = tmp_path / "app.db"
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(database_path))
    app = AppTest.from_file("app.py").run(timeout=30)
    next(
        button for button in app.button if button.label == "今すぐDBバックアップを作成"
    ).click()
    app.run(timeout=30)
    unreadable = tmp_path / "app.db.backups" / "unreadable.sqlite3"
    unreadable.write_bytes(b"placeholder")
    inspect_backup = SQLiteBackupService.inspect_backup

    def fail_one_inspection(self, path):
        if path.name == unreadable.name:
            raise PermissionError("simulated access denial")
        return inspect_backup(self, path)

    monkeypatch.setattr(SQLiteBackupService, "inspect_backup", fail_one_inspection)

    app.run(timeout=30)

    assert not app.exception
    assert any(
        "検査できないバックアップを復元候補から除外" in message.value
        and unreadable.name in message.value
        for message in app.warning
    )
    restore_select = next(
        widget for widget in app.selectbox if widget.label == "復元するバックアップ"
    )
    assert len(restore_select.options) == 1
    assert unreadable.is_file()


def test_app_scans_and_previews_vault(tmp_path, monkeypatch):
    vault = tmp_path / "Vault"
    vault.mkdir()
    (vault / "Example.md").write_text("# Rule\nReuse existing code.", encoding="utf-8")
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "app.db"))
    app = AppTest.from_file("app.py").run(timeout=30)

    vault_input = next(widget for widget in app.text_input if widget.label == "Vaultフォルダ")
    vault_input.set_value(str(vault))
    load_button = next(button for button in app.button if button.label == "Vaultを読み込む")
    load_button.click()
    app.run(timeout=30)

    assert not app.exception
    assert any("1件読み込みました" in message.value for message in app.success)
    assert any("Reuse existing code" in code.value for code in app.code)


def test_app_prepares_redacted_payload_without_network(tmp_path, monkeypatch):
    secret = "sk-proj-exampleSecretValue1234567890"
    vault = tmp_path / "Vault"
    vault.mkdir()
    (vault / "Example.md").write_text(f"# Rule\nkey={secret}", encoding="utf-8")
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "app.db"))
    app = AppTest.from_file("app.py").run(timeout=30)

    next(widget for widget in app.text_input if widget.label == "Vaultフォルダ").set_value(
        str(vault)
    )
    next(button for button in app.button if button.label == "Vaultを読み込む").click()
    app.run(timeout=30)
    next(
        widget
        for widget in app.multiselect
        if widget.label == "AI分析対象候補（まだ送信されません）"
    ).set_value(["Example.md"])
    app.run(timeout=30)
    next(button for button in app.button if button.label == "送信内容を準備する").click()
    app.run(timeout=30)

    payload_code = next(code.value for code in app.code if '"schema_version"' in code.value)
    assert secret not in payload_code
    assert "[REDACTED:openai_api_key]" in payload_code
    assert any("自動で伏字" in message.value for message in app.warning)
    live_button = next(
        button
        for button in app.button
        if button.label == "OpenAIで実抽出する（API料金が発生します）"
    )
    assert live_button.disabled is True
    assert any("入力推定" in item.value for item in app.markdown)
    assert any("上限目安" in item.value for item in app.markdown)

    next(
        checkbox
        for checkbox in app.checkbox
        if checkbox.label == "伏字済みの送信内容を確認しました"
    ).set_value(True)
    app.run(timeout=30)
    next(button for button in app.button if button.label == "モック抽出を実行する").click()
    app.run(timeout=30)

    with sqlite3.connect(tmp_path / "app.db") as connection:
        status = connection.execute("SELECT status FROM extraction_runs").fetchone()
        candidate_status = connection.execute(
            "SELECT status FROM skill_candidates"
        ).fetchone()
        generated_skills = connection.execute("SELECT COUNT(*) FROM skill_dna").fetchone()
    assert status == ("completed",)
    assert candidate_status == ("pending",)
    assert generated_skills == (0,)
    assert any(button.label == "承認する" for button in app.button)
    assert next(button for button in app.button if button.label == "承認する").disabled
    assert any("DNA Trace" in item.value for item in app.markdown)
    assert any(
        widget.label == "元メモに、このルールを直接支える内容がありますか？"
        for widget in app.selectbox
    )
    assert any(
        widget.label == "引用とルールの意味・条件は一致していますか？"
        for widget in app.selectbox
    )
    assert any(
        button.label == "このルールの確認結果を保存" for button in app.button
    )
    assert any("モック抽出が完了" in message.value for message in app.success)
    assert any("検証済みSkill候補" in item.value for item in app.markdown)
    assert any("これはAIが抽出した候補ではありません" in item.value for item in app.warning)

    # A candidate approved by an older app version must remain visible for re-review,
    # while downstream compilation excludes it until the current trace gate passes.
    with sqlite3.connect(tmp_path / "app.db") as connection:
        connection.execute("UPDATE skill_candidates SET status = 'approved'")
        connection.commit()
    app.run(timeout=30)

    assert not app.exception
    assert any("以前の版で承認済み" in item.value for item in app.warning)
    assert any("DNA Trace未完了のため除外" in item.value for item in app.warning)
    assert any("DNA Trace確認済み" in item.value for item in app.info)

    with sqlite3.connect(tmp_path / "app.db") as connection:
        connection.execute("UPDATE skill_candidates SET status = 'pending'")
        connection.commit()
    app.run(timeout=30)

    next(button for button in app.button if button.label == "モック抽出を実行する").click()
    app.run(timeout=30)
    merge_checkbox = next(
        checkbox
        for checkbox in app.checkbox
        if checkbox.label
        == "元の2候補を保留にし、統合結果を新しい未確認候補として保存します"
    )
    merge_checkbox.set_value(True)
    app.run(timeout=30)
    next(
        button for button in app.button if button.label == "未確認候補として統合"
    ).click()
    app.run(timeout=30)

    with sqlite3.connect(tmp_path / "app.db") as connection:
        candidate_statuses = connection.execute(
            "SELECT status FROM skill_candidates ORDER BY status"
        ).fetchall()
        merge_sources = connection.execute(
            "SELECT COUNT(*) FROM candidate_merge_sources"
        ).fetchone()
        generated_skills = connection.execute("SELECT COUNT(*) FROM skill_dna").fetchone()
    assert candidate_statuses == [("on_hold",), ("on_hold",), ("pending",)]
    assert merge_sources == (2,)
    assert generated_skills == (0,)
