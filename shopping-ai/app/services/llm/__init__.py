from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class LLMResult:
    text: str
    provider: str
    model: str


class LLMProviderError(RuntimeError):
    """Safe provider failure that does not expose SDK or credential details."""


class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        system_prompt: str | None = None,
    ) -> LLMResult:
        """Generate one assistant response without application side effects."""


class MockLLMProvider(LLMProvider):
    """Deterministic provider for tests and independent development."""

    def __init__(self, response_text: str = "How can I help you shop today?") -> None:
        self.response_text = response_text

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        system_prompt: str | None = None,
    ) -> LLMResult:
        del system_prompt
        if not messages:
            raise ValueError("At least one message is required")
        return LLMResult(text=self.response_text, provider="mock", model="deterministic")


class LLMService:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def reply(
        self,
        message: str,
        *,
        history: Sequence[LLMMessage] = (),
        system_prompt: str | None = None,
    ) -> LLMResult:
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("Message cannot be empty")
        messages = [*history, LLMMessage(role="user", content=normalized_message)]
        return await self._provider.generate(messages, system_prompt=system_prompt)


__all__ = [
    "LLMMessage",
    "LLMProvider",
    "LLMProviderError",
    "LLMResult",
    "LLMService",
    "MockLLMProvider",
]

