import pytest
from pydantic import ValidationError

from app.config import Settings


def test_safe_defaults_use_mock_provider() -> None:
    settings = Settings(_env_file=None)

    assert settings.llm_provider == "mock"
    assert str(settings.dotnet_base_url).rstrip("/") == "https://localhost:5000"
    assert settings.conversation_ttl_seconds == 86_400


def test_anthropic_provider_requires_key_and_model() -> None:
    with pytest.raises(ValidationError):
        Settings(llm_provider="anthropic", _env_file=None)


def test_anthropic_provider_accepts_complete_configuration() -> None:
    settings = Settings(
        llm_provider="anthropic",
        anthropic_api_key="test-key",
        anthropic_model="test-model",
        _env_file=None,
    )

    assert settings.anthropic_model == "test-model"


def test_production_requires_internal_key_and_redis() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", _env_file=None)
