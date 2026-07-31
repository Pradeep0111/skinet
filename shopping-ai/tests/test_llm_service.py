import pytest

from app.services.llm import LLMMessage, LLMService, MockLLMProvider


@pytest.mark.asyncio
async def test_mock_provider_is_deterministic() -> None:
    service = LLMService(MockLLMProvider("fixture response"))

    result = await service.reply(
        "show me fruit",
        history=[LLMMessage(role="assistant", content="What would you like?")],
    )

    assert result.text == "fixture response"
    assert result.provider == "mock"
    assert result.model == "deterministic"


@pytest.mark.asyncio
async def test_empty_message_is_rejected_before_provider_call() -> None:
    service = LLMService(MockLLMProvider())

    with pytest.raises(ValueError, match="cannot be empty"):
        await service.reply("   ")

