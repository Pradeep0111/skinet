import pytest
from pydantic import ValidationError

from app.config import Settings


def test_safe_defaults_use_mock_provider() -> None:
    settings = Settings(_env_file=None)

    assert settings.llm_provider == "mock"
    assert str(settings.dotnet_base_url).rstrip("/") == "https://localhost:5000"
    assert settings.conversation_ttl_seconds == 86_400
    assert settings.semantic_search_enabled is False
    assert settings.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"


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


@pytest.mark.parametrize("app_env", ["staging", "production"])
def test_deployed_semantic_search_requires_pinned_offline_model(app_env: str) -> None:
    production = {
        "app_env": app_env,
        "internal_service_key": "internal-key-long-enough",
        "dotnet_service_key": "catalog-key-long-enough",
        "conversation_backend": "redis",
        "dotnet_base_url": "https://catalog.example.com",
        "semantic_search_enabled": True,
        "_env_file": None,
    }

    with pytest.raises(ValidationError, match="EMBEDDING_REVISION"):
        Settings(**production, embedding_local_files_only=True)

    with pytest.raises(ValidationError, match="EMBEDDING_LOCAL_FILES_ONLY"):
        Settings(**production, embedding_revision="a" * 40)

    with pytest.raises(ValidationError, match="40-character commit SHA"):
        Settings(
            **production,
            embedding_revision="main",
            embedding_local_files_only=True,
        )

    settings = Settings(
        **production,
        embedding_revision="a" * 40,
        embedding_local_files_only=True,
    )
    assert settings.embedding_local_files_only is True
