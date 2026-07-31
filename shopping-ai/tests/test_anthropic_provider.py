from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.llm import LLMMessage
from app.services.llm.anthropic_provider import ClaudeProvider


@pytest.mark.asyncio
async def test_claude_provider_maps_messages_and_text_response() -> None:
    create = AsyncMock(
        return_value=SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Try the fresh bananas.")]
        )
    )
    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    provider = ClaudeProvider(
        api_key="test-key",
        model="test-model",
        max_tokens=256,
        timeout_seconds=5,
        client=client,
    )

    result = await provider.generate(
        [LLMMessage(role="user", content="Show me fruit")],
        system_prompt="Use only approved catalog data.",
    )

    assert result.text == "Try the fresh bananas."
    assert result.provider == "anthropic"
    assert result.model == "test-model"
    create.assert_awaited_once_with(
        model="test-model",
        max_tokens=256,
        messages=[{"role": "user", "content": "Show me fruit"}],
        system="Use only approved catalog data.",
    )

