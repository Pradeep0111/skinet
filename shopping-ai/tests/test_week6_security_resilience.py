import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from app.config import Settings
from app.errors import AssistantAPIError, unexpected_error_handler
from app.main import create_app
from app.observability import JsonFormatter, configure_logging
from app.security import require_internal_service_key
from app.services.conversation import InMemoryConversationStore
from app.services.llm import LLMMessage, LLMProviderError
from app.services.llm import anthropic_provider as anthropic_module
from app.services.llm.anthropic_provider import ClaudeProvider


def _deployed_settings(app_env: str, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": app_env,
        "internal_service_key": "internal-key-1234567890",
        "dotnet_service_key": "dotnet-key-123456789012",
        "dotnet_base_url": "https://catalog.example.test",
        "dotnet_verify_tls": True,
        "conversation_backend": "redis",
    }
    values.update(overrides)
    return Settings(**values, _env_file=None)


def _security_request(settings: Settings) -> Request:
    application = SimpleNamespace(state=SimpleNamespace(settings=settings))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/chat",
            "headers": [],
            "app": application,
        }
    )


def _claude_provider(create: AsyncMock) -> ClaudeProvider:
    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    return ClaudeProvider(
        api_key="test-key",
        model="test-model",
        max_tokens=256,
        timeout_seconds=5,
        client=client,
    )


@pytest.mark.parametrize(
    ("configured_key", "supplied_key"),
    [
        ("configured-secret", "wrong-secret"),
        ("s\u00ebcret-\U0001f510", "different-\U0001f510"),
    ],
)
@pytest.mark.asyncio
async def test_wrong_service_keys_are_safely_rejected(
    configured_key: str,
    supplied_key: str,
) -> None:
    settings = Settings(
        app_env="test",
        internal_service_key=configured_key,
        _env_file=None,
    )

    with pytest.raises(AssistantAPIError) as caught:
        await require_internal_service_key(
            _security_request(settings),
            x_assistant_service_key=supplied_key,
        )

    assert caught.value.status_code == 401
    assert caught.value.error_code == "invalid_service_key"
    assert configured_key not in str(caught.value)
    assert supplied_key not in str(caught.value)


@pytest.mark.asyncio
async def test_matching_non_ascii_service_key_does_not_raise_encoding_error() -> None:
    service_key = "s\u00ebcure-\U0001f510-service-key"
    settings = Settings(
        app_env="test",
        internal_service_key=service_key,
        _env_file=None,
    )

    result = await require_internal_service_key(
        _security_request(settings),
        x_assistant_service_key=service_key,
    )

    assert result is None


@pytest.mark.parametrize(
    ("configured_key", "expected_status", "expected_code"),
    [
        (None, 503, "assistant_not_configured"),
        ("configured-service-key", 401, "invalid_service_key"),
    ],
)
def test_chat_rejects_unconfigured_or_wrong_service_key(
    configured_key: str | None,
    expected_status: int,
    expected_code: str,
) -> None:
    settings = Settings(
        app_env="test",
        internal_service_key=configured_key,
        _env_file=None,
    )
    application = create_app(settings)

    with TestClient(application) as client:
        response = client.post(
            "/api/chat",
            json={"message": "Show me boots"},
            headers={"X-Assistant-Service-Key": "wrong-service-key"},
        )

    assert response.status_code == expected_status
    assert response.json()["errorCode"] == expected_code
    assert "wrong-service-key" not in response.text


@pytest.mark.parametrize("app_env", ["staging", "production"])
@pytest.mark.parametrize(
    ("setting_name", "value"),
    [
        ("internal_service_key", None),
        ("internal_service_key", "   "),
        ("internal_service_key", "too-short"),
        ("dotnet_service_key", None),
        ("dotnet_service_key", "   "),
        ("dotnet_service_key", "too-short"),
    ],
)
def test_deployed_environments_reject_missing_or_short_service_keys(
    app_env: str,
    setting_name: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError, match="at least 16 non-whitespace"):
        _deployed_settings(app_env, **{setting_name: value})


@pytest.mark.parametrize("app_env", ["staging", "production"])
def test_deployed_environments_require_redis(app_env: str) -> None:
    with pytest.raises(ValidationError, match="Redis conversation storage"):
        _deployed_settings(app_env, conversation_backend="memory")


@pytest.mark.parametrize("app_env", ["staging", "production"])
@pytest.mark.parametrize(
    "overrides",
    [
        {"dotnet_base_url": "http://catalog.example.test"},
        {"dotnet_verify_tls": False},
    ],
)
def test_deployed_environments_require_verified_https(
    app_env: str,
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="verified HTTPS"):
        _deployed_settings(app_env, **overrides)


@pytest.mark.parametrize("app_env", ["staging", "production"])
def test_deployed_environments_accept_complete_secure_configuration(app_env: str) -> None:
    settings = _deployed_settings(app_env)

    assert settings.app_env == app_env
    assert settings.conversation_backend == "redis"
    assert settings.dotnet_verify_tls is True


@pytest.mark.parametrize("app_env", ["staging", "production"])
def test_openapi_and_interactive_docs_are_disabled_when_deployed(app_env: str) -> None:
    settings = _deployed_settings(app_env)
    store = InMemoryConversationStore(ttl_seconds=settings.conversation_ttl_seconds)
    application = create_app(settings, conversation_store=store)

    with TestClient(application) as client:
        openapi_response = client.get("/openapi.json")
        docs_response = client.get("/docs")

    assert openapi_response.status_code == 404
    assert docs_response.status_code == 404


@pytest.mark.parametrize(
    "untrusted_request_id",
    [
        "not valid;secret=do-not-reflect",
        "x" * 65,
    ],
)
def test_untrusted_request_id_is_replaced_with_generated_uuid(
    untrusted_request_id: str,
) -> None:
    settings = Settings(app_env="test", _env_file=None)
    application = create_app(settings)

    with TestClient(application) as client:
        response = client.get(
            "/health",
            headers={"X-Request-ID": untrusted_request_id},
        )

    generated_request_id = response.headers["x-request-id"]
    assert response.status_code == 200
    assert generated_request_id != untrusted_request_id
    assert str(UUID(generated_request_id)) == generated_request_id


def test_json_formatter_excludes_unapproved_sensitive_fields() -> None:
    record = logging.LogRecord(
        name="shopping_ai.errors",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="unexpected_error",
        args=(),
        exc_info=None,
    )
    record.request_id = "request-001"
    record.exception_type = "RuntimeError"
    record.authorization = "Bearer must-not-appear"
    record.request_body = '{"message":"must-not-appear"}'

    serialized = JsonFormatter().format(record)
    payload = json.loads(serialized)

    assert payload["message"] == "unexpected_error"
    assert payload["request_id"] == "request-001"
    assert payload["exception_type"] == "RuntimeError"
    assert "authorization" not in payload
    assert "request_body" not in payload
    assert "must-not-appear" not in serialized


@pytest.mark.asyncio
async def test_unexpected_error_handler_returns_and_logs_only_safe_details(caplog) -> None:
    private_detail = "api-key=private-provider-value"
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/chat",
            "headers": [],
        }
    )
    request.state.request_id = "request-001"

    with caplog.at_level(logging.ERROR, logger="shopping_ai.errors"):
        response = await unexpected_error_handler(request, RuntimeError(private_detail))

    payload = json.loads(response.body)
    assert response.status_code == 500
    assert payload == {
        "errorCode": "internal_error",
        "message": "The shopping assistant could not process the request.",
        "retryable": True,
        "correlationId": "request-001",
    }
    assert private_detail not in response.body.decode()
    assert private_detail not in caplog.text
    assert any(
        record.exception_type == "RuntimeError"
        and record.getMessage() == "unexpected_error"
        and record.exc_info is None
        for record in caplog.records
    )


def test_http_client_loggers_are_limited_to_warning() -> None:
    configure_logging("INFO")

    for logger_name in ("httpx", "httpcore", "httpx2", "httpcore2"):
        assert logging.getLogger(logger_name).getEffectiveLevel() == logging.WARNING


@pytest.mark.asyncio
async def test_claude_provider_normalizes_sdk_error_without_private_detail(
    monkeypatch,
) -> None:
    class FakeAPIError(Exception):
        pass

    private_detail = "authorization=private-provider-key"
    monkeypatch.setattr(anthropic_module, "APIError", FakeAPIError)
    provider = _claude_provider(AsyncMock(side_effect=FakeAPIError(private_detail)))

    with pytest.raises(LLMProviderError) as caught:
        await provider.generate([LLMMessage(role="user", content="Show me fruit")])

    assert str(caught.value) == "Claude request failed"
    assert private_detail not in str(caught.value)


@pytest.mark.parametrize(
    "content",
    [
        [],
        [SimpleNamespace(type="tool_use", text="private non-text content")],
        [SimpleNamespace(type="text", text="   ")],
    ],
)
@pytest.mark.asyncio
async def test_claude_provider_rejects_empty_or_non_text_response(content: list[object]) -> None:
    provider = _claude_provider(
        AsyncMock(return_value=SimpleNamespace(content=content))
    )

    with pytest.raises(LLMProviderError, match="returned no text content"):
        await provider.generate([LLMMessage(role="user", content="Show me fruit")])
