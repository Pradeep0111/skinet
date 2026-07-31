from functools import lru_cache
from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or an untracked .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "skinet-shopping-ai"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"

    llm_provider: Literal["mock", "anthropic"] = "mock"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str | None = None
    anthropic_max_tokens: int = Field(default=512, ge=64, le=4_096)

    dotnet_base_url: AnyHttpUrl = AnyHttpUrl("https://localhost:5000")
    dotnet_service_key: SecretStr | None = None
    internal_service_key: SecretStr | None = None
    conversation_backend: Literal["memory", "redis"] = "memory"
    redis_url: str = "redis://localhost:6379/0"
    conversation_ttl_seconds: int = Field(default=86_400, ge=300, le=604_800)
    conversation_max_messages: int = Field(default=20, ge=2, le=100)
    request_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    max_message_length: int = Field(default=1_000, ge=1, le=10_000)

    @model_validator(mode="after")
    def validate_provider_settings(self) -> Self:
        if self.llm_provider == "anthropic":
            if self.anthropic_api_key is None or not self.anthropic_api_key.get_secret_value():
                raise ValueError("ANTHROPIC_API_KEY is required for the anthropic provider")
            if not self.anthropic_model:
                raise ValueError("ANTHROPIC_MODEL is required for the anthropic provider")
        if self.app_env in {"staging", "production"}:
            if self.internal_service_key is None:
                raise ValueError("INTERNAL_SERVICE_KEY is required outside development and test")
            if self.conversation_backend != "redis":
                raise ValueError(
                    "Redis conversation storage is required outside development and test"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
