import pytest
from pydantic import SecretStr, ValidationError

from devflow_core.config import Settings, get_settings
from tests.conftest import ROOT


def test_defaults_and_optional_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENVIRONMENT")
    monkeypatch.delenv("DATABASE_URL")
    settings = Settings()
    assert settings.ENVIRONMENT == "development"
    assert settings.DEVFLOW_API_BASE_URL == "http://localhost:8000"
    assert settings.DATABASE_URL == "sqlite+aiosqlite:///./devflow.db"
    assert settings.CHATGPT_API_KEY is settings.CODEX_API_KEY is settings.GITHUB_TOKEN is None
    assert settings.ANTHROPIC_API_KEY is settings.FIGMA_TOKEN is None
    assert "NOTEBOOKLM_API_KEY" not in Settings.model_fields


@pytest.mark.parametrize("environment", ["development", "local", "test", "staging", "production"])
def test_supported_environments(monkeypatch: pytest.MonkeyPatch, environment: str) -> None:
    monkeypatch.setenv("ENVIRONMENT", environment)
    assert Settings().ENVIRONMENT == environment


def test_invalid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "invalid")
    with pytest.raises(ValidationError, match="ENVIRONMENT"):
        Settings()


def test_secrets_and_url_override(monkeypatch: pytest.MonkeyPatch, synthetic_secret: str) -> None:
    monkeypatch.setenv("CODEX_API_KEY", synthetic_secret)
    monkeypatch.setenv("DEVFLOW_API_BASE_URL", "http://localhost:8800")
    settings = Settings()
    assert isinstance(settings.CODEX_API_KEY, SecretStr)
    assert settings.CODEX_API_KEY.get_secret_value() == synthetic_secret
    assert synthetic_secret not in str(settings) and synthetic_secret not in repr(settings)
    assert settings.DEVFLOW_API_BASE_URL == "http://localhost:8800"


def test_cache_can_be_refreshed(monkeypatch: pytest.MonkeyPatch) -> None:
    first = get_settings()
    assert first is get_settings()
    monkeypatch.setenv("APP_NAME", "Fresh configuration")
    assert get_settings() is first
    get_settings.cache_clear()
    assert get_settings().APP_NAME == "Fresh configuration"
    assert get_settings() is not first


def test_dotenv_template_matches_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from dotenv import dotenv_values

    template = ROOT / ".env.example"
    assert dotenv_values(template).keys() == Settings.model_fields.keys()
    monkeypatch.delenv("ENVIRONMENT")
    assert Settings(_env_file=template).ENVIRONMENT == "development"
