from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from platformdirs import user_data_path
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and `.env.local`."""

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        env_prefix="SKILL_DNA_",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_name: str = "Skill DNA Compiler"
    environment: Literal["development", "test", "production"] = "development"
    database_path: Path | None = None
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Keep the conventional OpenAI variable name while namespacing app settings.
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = "gpt-5.6-terra"
    openai_reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = (
        "medium"
    )
    openai_max_output_tokens: int = Field(default=6_000, ge=500, le=128_000)
    max_input_chars: int = Field(default=60_000, ge=1_000, le=1_000_000)

    @property
    def resolved_database_path(self) -> Path:
        if self.database_path is not None:
            return self.database_path.expanduser().resolve()
        return user_data_path("SkillDNACompiler", "SkillDNACompiler") / "skill-dna.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    if os.environ.get("SKILL_DNA_ENVIRONMENT", "").lower() == "production":
        return Settings(_env_file=None)
    return Settings()
