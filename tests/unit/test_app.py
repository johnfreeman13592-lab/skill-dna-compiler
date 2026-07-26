import sqlite3
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app as app_module
from skill_dna_compiler import __release_label__
from skill_dna_compiler.config.settings import get_settings

PROJECT_ROOT = Path(__file__).parents[2]


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _click(app: AppTest, label: str) -> AppTest:
    next(button for button in app.button if button.label == label).click()
    return app.run(timeout=30)


def _open_notes(app: AppTest) -> AppTest:
    return _click(app, "Use my notes")


def _open_settings(app: AppTest) -> AppTest:
    return _click(app, "Settings")


def test_app_renders_phase_two_vault_controls(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "app.db"))

    app = AppTest.from_file("app.py").run(timeout=30)

    assert not app.exception
    assert any(
        "Turn your notes into instructions your AI can reuse" in item.value
        for item in app.title
    )
    assert any(button.label == "Try the sample" for button in app.button)
    assert any(button.label == "Use my notes" for button in app.button)
    assert not any(widget.label == "Vault folder" for widget in app.text_input)

    _open_notes(app)
    assert any(widget.label == "Vault folder" for widget in app.text_input)
    assert any(button.label == "Load Vault" for button in app.button)
    assert not next(button for button in app.button if "Vault" in button.label).disabled

    _open_settings(app)
    assert any(button.label == "Create database backup now" for button in app.button)
    assert any("OpenAI API key settings" in item.value for item in app.subheader)
    assert any(__release_label__ in item.value for item in app.markdown)


def test_app_defaults_to_english_and_switches_ui_language(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "app.db"))
    app = AppTest.from_file("app.py").run(timeout=30)

    language = next(widget for widget in app.selectbox if widget.label == "Language")
    assert language.value == "en"
    assert language.options == ["English", "日本語"]
    assert any(
        "Turn your notes into instructions your AI can reuse" in item.value
        for item in app.title
    )

    language.set_value("ja")
    app.run(timeout=30)
    assert not app.exception
    assert any(
        "メモを、AIが繰り返し使える作業ルールに" in item.value for item in app.title
    )
    next(button for button in app.button if button.label == "設定").click()
    app.run(timeout=30)
    assert [tab.label for tab in app.tabs] == [
        "言語",
        "OpenAI API",
        "データとバックアップ",
        "安全性の詳細",
        "フィードバックと履歴",
    ]
    next(button for button in app.button if button.label == "English").click()
    app.run(timeout=30)
    assert any(item.value == "Settings" for item in app.title)


def test_packaged_sample_vault_resolves_next_to_executable(tmp_path, monkeypatch):
    executable = tmp_path / "Skill DNA Compiler.exe"
    executable.touch()
    sample_vault = tmp_path / "Sample Vault"
    sample_vault.mkdir()
    monkeypatch.delenv("SKILL_DNA_SAMPLE_VAULT_PATH", raising=False)
    monkeypatch.setattr(app_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(app_module.sys, "executable", str(executable))

    assert app_module._bundled_sample_vault() == sample_vault.resolve()


def test_sample_vault_shortcut_only_fills_path_until_user_loads(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "app.db"
    sample_vault = PROJECT_ROOT / "tests" / "fixtures" / "sample_vault"
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("SKILL_DNA_SAMPLE_VAULT_PATH", str(sample_vault))
    app = AppTest.from_file("app.py").run(timeout=30)
    _open_notes(app)

    next(
        button for button in app.button if button.label == "Use bundled Sample Vault"
    ).click()
    app.run(timeout=30)

    assert not app.exception
    assert next(
        widget for widget in app.text_input if widget.label == "Vault folder"
    ).value == str(sample_vault)
    assert any("Press **Load Vault**" in item.value for item in app.info)
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM vaults").fetchone() == (0,)

    next(button for button in app.button if button.label == "Load Vault").click()
    app.run(timeout=30)

    assert not app.exception
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM vaults").fetchone() == (1,)


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
    assert any(
        "Turn your notes into instructions your AI can reuse" in item.value
        for item in app.title
    )
    assert not list(tmp_path.rglob("SKILL.md"))

    _open_settings(app)
    assert any("OPENAI_API_KEY" in message.value for message in app.warning)


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
    _open_settings(app)

    save_button = next(
        button
        for button in app.button
        if button.label == "Save to Windows Credential Manager"
    )
    assert not save_button.disabled

    key_input = next(widget for widget in app.text_input if widget.label == "OpenAI API key")
    key_input.set_value(test_key)
    app.run(timeout=30)
    next(
        button
        for button in app.button
        if button.label == "Save to Windows Credential Manager"
    ).click()
    app.run(timeout=30)

    assert not app.exception
    assert stored
    assert test_key.encode() not in database_path.read_bytes()
    assert any("No API request was made" in item.value for item in app.success)
    assert next(
        widget for widget in app.text_input if widget.label == "OpenAI API key"
    ).value == ""

    next(
        checkbox
        for checkbox in app.checkbox
        if checkbox.label == "I confirm that I want to delete the saved API key"
    ).set_value(True)
    app.run(timeout=30)
    next(
        button
        for button in app.button
        if button.label == "Delete from Windows Credential Manager"
    ).click()
    app.run(timeout=30)

    assert not app.exception
    assert not stored
    assert any("Deleted the saved API key" in item.value for item in app.success)


def test_app_reports_missing_vault_in_clean_temporary_environment(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "clean-app.db"))
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py")).run(timeout=30)
    _open_notes(app)

    missing_vault = tmp_path / "missing-vault"
    next(widget for widget in app.text_input if widget.label == "Vault folder").set_value(
        str(missing_vault)
    )
    app.run(timeout=30)
    next(button for button in app.button if button.label == "Load Vault").click()
    app.run(timeout=30)

    assert not app.exception
    assert any("Vault does not exist" in message.value for message in app.error)
    assert not missing_vault.exists()


def test_app_creates_validated_manual_database_backup(tmp_path, monkeypatch):
    database_path = tmp_path / "app.db"
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(database_path))
    app = AppTest.from_file("app.py").run(timeout=30)
    _open_settings(app)

    next(
        button for button in app.button if button.label == "Create database backup now"
    ).click()
    app.run(timeout=30)

    backup_directory = tmp_path / "app.db.backups"
    backups = list(backup_directory.glob("*.sqlite3"))
    assert not app.exception
    assert len(backups) == 1
    assert any("validated backup" in message.value for message in app.success)
    restore_button = next(
        button for button in app.button if button.label == "Restore selected database backup"
    )
    assert restore_button.disabled is True


def test_app_lists_corrupt_backup_without_offering_it_for_restore(tmp_path, monkeypatch):
    database_path = tmp_path / "app.db"
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(database_path))
    app = AppTest.from_file("app.py").run(timeout=30)
    _open_settings(app)
    next(
        button for button in app.button if button.label == "Create database backup now"
    ).click()
    app.run(timeout=30)
    backup_directory = tmp_path / "app.db.backups"
    corrupt = backup_directory / "corrupt.sqlite3"
    corrupt.write_bytes(b"not a sqlite database")

    app.run(timeout=30)

    assert not app.exception
    restore_select = next(
        widget for widget in app.selectbox if widget.label == "Backup to restore"
    )
    assert len(restore_select.options) == 1
    assert "corrupt.sqlite3" not in restore_select.options
    assert any("Corrupt or unreadable" in str(table.value) for table in app.dataframe)
    assert corrupt.is_file()


def test_app_skips_permission_denied_backup_without_deleting_it(tmp_path, monkeypatch):
    from skill_dna_compiler.storage.backups import SQLiteBackupService

    database_path = tmp_path / "app.db"
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(database_path))
    app = AppTest.from_file("app.py").run(timeout=30)
    _open_settings(app)
    next(
        button for button in app.button if button.label == "Create database backup now"
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
        "Excluded backups that could not be inspected" in message.value
        and unreadable.name in message.value
        for message in app.warning
    )
    restore_select = next(
        widget for widget in app.selectbox if widget.label == "Backup to restore"
    )
    assert len(restore_select.options) == 1
    assert unreadable.is_file()


def test_app_scans_and_previews_vault(tmp_path, monkeypatch):
    vault = tmp_path / "Vault"
    vault.mkdir()
    (vault / "Example.md").write_text("# Rule\nReuse existing code.", encoding="utf-8")
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "app.db"))
    app = AppTest.from_file("app.py").run(timeout=30)
    _open_notes(app)

    vault_input = next(widget for widget in app.text_input if widget.label == "Vault folder")
    vault_input.set_value(str(vault))
    load_button = next(button for button in app.button if button.label == "Load Vault")
    load_button.click()
    app.run(timeout=30)

    assert not app.exception
    assert any("Loaded 1 Markdown note" in message.value for message in app.success)
    assert any("Reuse existing code" in code.value for code in app.code)


def test_app_prepares_redacted_payload_without_network(tmp_path, monkeypatch):
    secret = "sk-proj-exampleSecretValue1234567890"
    vault = tmp_path / "Vault"
    vault.mkdir()
    (vault / "Example.md").write_text(f"# Rule\nkey={secret}", encoding="utf-8")
    monkeypatch.setenv("SKILL_DNA_DATABASE_PATH", str(tmp_path / "app.db"))
    app = AppTest.from_file("app.py").run(timeout=30)
    _open_notes(app)

    next(widget for widget in app.text_input if widget.label == "Vault folder").set_value(
        str(vault)
    )
    next(button for button in app.button if button.label == "Load Vault").click()
    app.run(timeout=30)
    next(
        widget
        for widget in app.multiselect
        if widget.label == "Notes to analyze (not sent yet)"
    ).set_value(["Example.md"])
    app.run(timeout=30)
    _click(app, "Continue to data review")
    next(button for button in app.button if button.label == "Prepare outbound content").click()
    app.run(timeout=30)

    payload_code = next(code.value for code in app.code if '"schema_version"' in code.value)
    assert secret not in payload_code
    assert "[REDACTED:openai_api_key]" in payload_code
    assert any("automatically redacted" in message.value for message in app.warning)
    live_button = next(
        button
        for button in app.button
        if button.label == "Extract with OpenAI (API charges may apply)"
    )
    assert live_button.disabled is True
    assert any("Estimated input" in item.value for item in app.markdown)
    assert any("Conservative maximum" in item.value for item in app.markdown)

    next(
        checkbox
        for checkbox in app.checkbox
        if checkbox.label == "I reviewed the redacted outbound content"
    ).set_value(True)
    app.run(timeout=30)
    next(button for button in app.button if button.label == "Run mock extraction").click()
    app.run(timeout=30)
    assert any("Mock extraction completed" in message.value for message in app.success)
    _click(app, "Continue to draft review")

    with sqlite3.connect(tmp_path / "app.db") as connection:
        status = connection.execute("SELECT status FROM extraction_runs").fetchone()
        candidate_status = connection.execute(
            "SELECT status FROM skill_candidates"
        ).fetchone()
        generated_skills = connection.execute("SELECT COUNT(*) FROM skill_dna").fetchone()
    assert status == ("completed",)
    assert candidate_status == ("pending",)
    assert generated_skills == (0,)
    assert any(button.label == "Approve" for button in app.button)
    assert next(button for button in app.button if button.label == "Approve").disabled
    assert any("DNA Trace" in item.value for item in app.markdown)
    assert any(
        widget.label == "Does the source note directly support this rule?"
        for widget in app.selectbox
    )
    assert any(
        widget.label
        == "Do the citation and rule have the same meaning and conditions?"
        for widget in app.selectbox
    )
    assert any(
        button.label == "Save this rule review" for button in app.button
    )
    assert any("Check each draft against your notes" in item.value for item in app.title)

    # A candidate approved by an older app version must remain visible for re-review,
    # while downstream compilation excludes it until the current trace gate passes.
    with sqlite3.connect(tmp_path / "app.db") as connection:
        connection.execute("UPDATE skill_candidates SET status = 'approved'")
        connection.commit()
    app.run(timeout=30)

    assert not app.exception
    assert any("approved by an older version" in item.value for item in app.warning)
    assert next(
        button for button in app.button if button.label == "4. Save and use"
    ).disabled

    with sqlite3.connect(tmp_path / "app.db") as connection:
        connection.execute("UPDATE skill_candidates SET status = 'pending'")
        connection.commit()
    app.run(timeout=30)

    _click(app, "2. Check data")
    next(button for button in app.button if button.label == "Run mock extraction").click()
    app.run(timeout=30)
    _click(app, "Continue to draft review")
    assert not any(
        checkbox.label
        == "Put both source candidates on hold and save the merge as a new Pending candidate"
        for checkbox in app.checkbox
    )

    with sqlite3.connect(tmp_path / "app.db") as connection:
        candidate_statuses = connection.execute(
            "SELECT status FROM skill_candidates ORDER BY status"
        ).fetchall()
        merge_sources = connection.execute(
            "SELECT COUNT(*) FROM candidate_merge_sources"
        ).fetchone()
        generated_skills = connection.execute("SELECT COUNT(*) FROM skill_dna").fetchone()
    assert candidate_statuses == [("pending",), ("pending",)]
    assert merge_sources == (0,)
    assert generated_skills == (0,)
