import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import monotonic
from typing import Literal

from redis.asyncio import Redis

from app.config import Settings

MAX_STORED_MESSAGES = 100
MAX_STORED_CONTENT_LENGTH = 10_000


class ConversationCorruptError(ValueError):
    """Stored conversation data is malformed and must not be trusted."""


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    """Stored transcript entry with application-produced product references."""

    role: Literal["user", "assistant"]
    content: str
    product_ids: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.role not in {"user", "assistant"}:
            raise ValueError("Unsupported conversation role")
        if not isinstance(self.content, str):
            raise ValueError("Conversation content must be text")
        if len(self.content) > MAX_STORED_CONTENT_LENGTH:
            raise ValueError("Conversation content is too long")
        if len(self.product_ids) > 10:
            raise ValueError("Conversation product context cannot exceed 10 products")
        if any(
            type(product_id) is not int or product_id <= 0
            for product_id in self.product_ids
        ):
            raise ValueError("Conversation product IDs must be positive integers")
        if len(set(self.product_ids)) != len(self.product_ids):
            raise ValueError("Conversation product IDs must be unique")


class ConversationStore(ABC):
    @abstractmethod
    async def get(self, conversation_id: str) -> list[ConversationMessage]:
        """Return stored messages, or an empty list for a new/expired conversation."""

    @abstractmethod
    async def save(
        self,
        conversation_id: str,
        messages: Sequence[ConversationMessage],
    ) -> None:
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
        self._items: dict[str, tuple[float, list[ConversationMessage]]] = {}

    async def get(self, conversation_id: str) -> list[ConversationMessage]:
        stored = self._items.get(conversation_id)
        if stored is None:
            return []
        expires_at, messages = stored
        if expires_at <= self._clock():
            self._items.pop(conversation_id, None)
            return []
        return list(messages)

    async def save(
        self,
        conversation_id: str,
        messages: Sequence[ConversationMessage],
    ) -> None:
        if len(messages) > MAX_STORED_MESSAGES:
            raise ValueError("Conversation history exceeds the storage limit")
        expires_at = self._clock() + self._ttl_seconds
        self._items[conversation_id] = (expires_at, list(messages))

    async def close(self) -> None:
        return None


class RedisConversationStore(ConversationStore):
    KEY_PREFIX = "assistant:conversation:"

    def __init__(self, redis: Redis, *, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def get(self, conversation_id: str) -> list[ConversationMessage]:
        payload = await self._redis.get(self._key(conversation_id))
        if payload is None:
            return []
        try:
            values = json.loads(payload)
            if not isinstance(values, list) or len(values) > MAX_STORED_MESSAGES:
                raise ValueError("Invalid conversation payload")
            messages = []
            for value in values:
                if not isinstance(value, dict):
                    raise ValueError("Invalid conversation entry")
                product_ids = value.get("product_ids", [])
                if not isinstance(product_ids, list):
                    raise ValueError("Invalid conversation product context")
                messages.append(
                    ConversationMessage(
                        role=value["role"],
                        content=value["content"],
                        product_ids=tuple(product_ids),
                    )
                )
            return messages
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ConversationCorruptError("Stored conversation data is invalid") from exc

    async def save(
        self,
        conversation_id: str,
        messages: Sequence[ConversationMessage],
    ) -> None:
        if len(messages) > MAX_STORED_MESSAGES:
            raise ValueError("Conversation history exceeds the storage limit")
        values = []
        for message in messages:
            value: dict[str, object] = {
                "role": message.role,
                "content": message.content,
            }
            if message.product_ids:
                value["product_ids"] = list(message.product_ids)
            values.append(value)
        payload = json.dumps(values, separators=(",", ":"))
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
