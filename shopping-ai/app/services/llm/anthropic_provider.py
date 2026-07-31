from collections.abc import Sequence
from typing import Any

from anthropic import APIError, AsyncAnthropic

from app.services.llm import LLMMessage, LLMProvider, LLMProviderError, LLMResult


class ClaudeProvider(LLMProvider):
    """Anthropic implementation of the provider-neutral LLM interface."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_tokens: int,
        timeout_seconds: float,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = client or AsyncAnthropic(api_key=api_key, timeout=timeout_seconds)

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        system_prompt: str | None = None,
    ) -> LLMResult:
        if not messages:
            raise ValueError("At least one message is required")

        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
        }
        if system_prompt:
            request["system"] = system_prompt

        try:
            response = await self._client.messages.create(**request)
        except APIError as exc:
            raise LLMProviderError("Claude request failed") from exc

        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
        if not text:
            raise LLMProviderError("Claude returned no text content")
        return LLMResult(text=text, provider="anthropic", model=self._model)

