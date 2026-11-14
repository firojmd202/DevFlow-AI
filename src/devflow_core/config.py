"""Application settings loaded from the environment and local dotenv file."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    APP_NAME: str = "DevFlow AI"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "local", "test", "staging", "production"] = "development"

    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    UI_HOST: str = "127.0.0.1"
    UI_PORT: int = 8501
    ALLOWED_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:8501"])
    DEVFLOW_API_BASE_URL: str = "http://localhost:8000"

    DATABASE_URL: str = "sqlite+aiosqlite:///./devflow.db"
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["text", "json"] = "text"

    CHATGPT_API_KEY: SecretStr | None = None
    CODEX_API_KEY: SecretStr | None = None
    ANTHROPIC_API_KEY: SecretStr | None = None
    GITHUB_TOKEN: SecretStr | None = None
    FIGMA_TOKEN: SecretStr | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    MCP_SERVERS_CONFIG: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
