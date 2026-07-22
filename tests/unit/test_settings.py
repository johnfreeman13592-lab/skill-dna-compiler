from pydantic import SecretStr

from skill_dna_compiler.config.settings import Settings, get_settings


def test_settings_resolve_explicit_database_path(tmp_path):
    database_path = tmp_path / "app.db"
    settings = Settings(_env_file=None, database_path=database_path)

    assert settings.resolved_database_path == database_path.resolve()
    assert settings.openai_model == "gpt-5.6-terra"
    assert settings.openai_max_output_tokens == 6_000
    assert settings.max_input_chars == 60_000


def test_api_key_uses_secret_type():
    settings = Settings(_env_file=None, openai_api_key="sk-example_secret_123456789")

    assert isinstance(settings.openai_api_key, SecretStr)
    assert "example_secret" not in str(settings.openai_api_key)


def test_production_settings_do_not_read_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env.local").write_text(
        "OPENAI_API_KEY=sk-proj-must-not-be-read\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SKILL_DNA_ENVIRONMENT", "production")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()

    try:
        settings = get_settings()

        assert settings.environment == "production"
        assert settings.openai_api_key is None
    finally:
        get_settings.cache_clear()
