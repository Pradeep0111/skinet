import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.conversation import InMemoryConversationStore
from app.services.llm import LLMMessage, LLMResult, MockLLMProvider

FIXTURES = Path(__file__).parent / "fixtures"


class RecordingProvider(MockLLMProvider):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[list[LLMMessage]] = []

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        system_prompt: str | None = None,
    ) -> LLMResult:
        del system_prompt
        self.calls.append(list(messages))
        return LLMResult(text="Mock shopping response", provider="mock", model="test")


def _settings(**overrides: object) -> Settings:
    return Settings(
        app_env="test",
        internal_service_key="test-secret",
        **overrides,
        _env_file=None,
    )


def test_internal_chat_requires_service_key() -> None:
    application = create_app(_settings())

    with TestClient(application) as client:
        response = client.post("/api/chat", json={"message": "Show me fruit"})

    assert response.status_code == 401
    assert response.json()["errorCode"] == "invalid_service_key"


def test_internal_chat_stores_bounded_multi_turn_history() -> None:
    provider = RecordingProvider()
    store = InMemoryConversationStore(ttl_seconds=60)
    application = create_app(
        _settings(conversation_max_messages=4),
        llm_provider=provider,
        conversation_store=store,
    )
    payload = json.loads(
        (FIXTURES / "internal_chat_request.json").read_text(encoding="utf-8")
    )
    headers = {"X-Assistant-Service-Key": "test-secret"}

    with TestClient(application) as client:
        first = client.post("/api/chat", json=payload, headers=headers)
        payload["message"] = "What else?"
        second = client.post("/api/chat", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["products"] == []
    assert first.json()["proposedActions"] == []
    assert len(provider.calls[0]) == 1
    assert len(provider.calls[1]) == 3


def test_internal_chat_rejects_pii_and_unknown_fields() -> None:
    application = create_app(_settings())
    payload = {
        "message": "Recommend something",
        "shopper": {"isAuthenticated": True, "email": "private@example.com"},
    }

    with TestClient(application) as client:
        response = client.post(
            "/api/chat",
            json=payload,
            headers={"X-Assistant-Service-Key": "test-secret"},
        )

    assert response.status_code == 422
    assert response.json()["errorCode"] == "invalid_request"
    assert "private@example.com" not in response.text


def test_internal_chat_honors_configured_message_limit() -> None:
    application = create_app(_settings(max_message_length=5))

    with TestClient(application) as client:
        response = client.post(
            "/api/chat",
            json={"message": "too long"},
            headers={"X-Assistant-Service-Key": "test-secret"},
        )

    assert response.status_code == 422
    assert response.json()["errorCode"] == "invalid_request"

