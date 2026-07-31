import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import asdict
from time import monotonic

from redis.asyncio import Redis

from app.config import Settings
from app.services.llm import LLMMessage


class ConversationStore(ABC):
    @abstractmethod
    async def get(self, conversation_id: str) -> list[LLMMessage]:
        """Return stored messages, or an empty list for a new/expired conversation."""

    @abstractmethod
    async def save(self, conversation_id: str, messages: Sequence[LLMMessage]) -> None:
        """Replace conversation history and refresh its TTL."""

    @abstractmethod
    async def close(self) -> None:
        """Release backend resources when the application stops."""


class InMemoryConversationStore(ConversationStore):
    def __init__(
        self,
        *,
        ttl_seconds: int,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._items: dict[str, tuple[float, list[LLMMessage]]] = {}

    async def get(self, conversation_id: str) -> list[LLMMessage]:
        stored = self._items.get(conversation_id)
        if stored is None:
            return []
        expires_at, messages = stored
        if expires_at <= self._clock():
            self._items.pop(conversation_id, None)
            return []
        return list(messages)

    async def save(self, conversation_id: str, messages: Sequence[LLMMessage]) -> None:
        expires_at = self._clock() + self._ttl_seconds
        self._items[conversation_id] = (expires_at, list(messages))

    async def close(self) -> None:
        return None


class RedisConversationStore(ConversationStore):
    KEY_PREFIX = "assistant:conversation:"

    def __init__(self, redis: Redis, *, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def get(self, conversation_id: str) -> list[LLMMessage]:
        payload = await self._redis.get(self._key(conversation_id))
        if payload is None:
            return []
        values = json.loads(payload)
        return [LLMMessage(role=value["role"], content=value["content"]) for value in values]

    async def save(self, conversation_id: str, messages: Sequence[LLMMessage]) -> None:
        payload = json.dumps([asdict(message) for message in messages], separators=(",", ":"))
        await self._redis.set(
            self._key(conversation_id),
            payload,
            ex=self._ttl_seconds,
        )

    async def close(self) -> None:
        await self._redis.aclose()

    @classmethod
    def from_url(cls, url: str, *, ttl_seconds: int) -> "RedisConversationStore":
        redis = Redis.from_url(url, decode_responses=True)
        return cls(redis, ttl_seconds=ttl_seconds)

    @classmethod
    def _key(cls, conversation_id: str) -> str:
        return f"{cls.KEY_PREFIX}{conversation_id}"


def create_conversation_store(settings: Settings) -> ConversationStore:
    if settings.conversation_backend == "redis":
        return RedisConversationStore.from_url(
            settings.redis_url,
            ttl_seconds=settings.conversation_ttl_seconds,
        )
    return InMemoryConversationStore(ttl_seconds=settings.conversation_ttl_seconds)
