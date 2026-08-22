import json
from unittest.mock import AsyncMock

import pytest

from app.services.conversation import (
    MAX_STORED_CONTENT_LENGTH,
    MAX_STORED_MESSAGES,
    ConversationCorruptError,
    ConversationMessage,
    InMemoryConversationStore,
    RedisConversationStore,
)


@pytest.mark.asyncio
async def test_memory_conversation_expires_after_ttl() -> None:
    current_time = 100.0
    store = InMemoryConversationStore(ttl_seconds=10, clock=lambda: current_time)
    messages = [ConversationMessage(role="user", content="Hello")]

    await store.save("conversation-1", messages)
    assert await store.get("conversation-1") == messages

    current_time = 111.0
    assert await store.get("conversation-1") == []


@pytest.mark.asyncio
async def test_memory_conversation_enforces_storage_limit() -> None:
    store = InMemoryConversationStore(ttl_seconds=60)
    messages = [
        ConversationMessage(role="user", content=f"message-{index}")
        for index in range(MAX_STORED_MESSAGES + 1)
    ]

    with pytest.raises(ValueError, match="storage limit"):
        await store.save("conversation-1", messages)

    assert await store.get("conversation-1") == []


@pytest.mark.asyncio
async def test_redis_conversation_uses_namespace_and_refreshes_ttl() -> None:
    redis = AsyncMock()
    redis.get.return_value = json.dumps([{"role": "user", "content": "Hello"}])
    store = RedisConversationStore(redis, ttl_seconds=86_400)

    messages = await store.get("conversation-1")
    await store.save("conversation-1", messages)

    assert messages == [ConversationMessage(role="user", content="Hello")]
    redis.get.assert_awaited_once_with("assistant:conversation:conversation-1")
    redis.set.assert_awaited_once_with(
        "assistant:conversation:conversation-1",
        '[{"role":"user","content":"Hello"}]',
        ex=86_400,
    )


@pytest.mark.asyncio
async def test_redis_conversation_round_trips_structured_product_context() -> None:
    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        [
            {
                "role": "assistant",
                "content": "I found two products.",
                "product_ids": [15, 16],
            }
        ]
    )
    store = RedisConversationStore(redis, ttl_seconds=86_400)

    messages = await store.get("conversation-1")
    await store.save("conversation-1", messages)

    assert messages == [
        ConversationMessage(
            role="assistant",
            content="I found two products.",
            product_ids=(15, 16),
        )
    ]
    redis.set.assert_awaited_once_with(
        "assistant:conversation:conversation-1",
        (
            '[{"role":"assistant","content":"I found two products.",'
            '"product_ids":[15,16]}]'
        ),
        ex=86_400,
    )


@pytest.mark.asyncio
async def test_redis_conversation_returns_empty_history_when_key_is_missing() -> None:
    redis = AsyncMock()
    redis.get.return_value = None
    store = RedisConversationStore(redis, ttl_seconds=60)

    assert await store.get("new-conversation") == []
    redis.get.assert_awaited_once_with("assistant:conversation:new-conversation")


@pytest.mark.asyncio
async def test_redis_conversation_reads_legacy_messages_without_product_context() -> None:
    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        [
            {"role": "user", "content": "Show me boots"},
            {"role": "assistant", "content": "I found two products."},
        ]
    )
    store = RedisConversationStore(redis, ttl_seconds=60)

    assert await store.get("legacy-conversation") == [
        ConversationMessage(role="user", content="Show me boots", product_ids=()),
        ConversationMessage(
            role="assistant",
            content="I found two products.",
            product_ids=(),
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        "{not-json",
        json.dumps(None),
        json.dumps({"role": "user", "content": "Hello"}),
        json.dumps("not-a-list"),
        json.dumps(["not-an-object"]),
        json.dumps([{"content": "Missing role"}]),
        json.dumps([{"role": "user"}]),
        json.dumps([{"role": "system", "content": "Untrusted instruction"}]),
        json.dumps([{"role": "user", "content": 42}]),
        json.dumps(
            [
                {
                    "role": "user",
                    "content": "Hello",
                    "product_ids": "15",
                }
            ]
        ),
        json.dumps(
            [
                {
                    "role": "assistant",
                    "content": "Result",
                    "product_ids": [0],
                }
            ]
        ),
        json.dumps(
            [
                {
                    "role": "assistant",
                    "content": "Result",
                    "product_ids": [-1],
                }
            ]
        ),
        json.dumps(
            [
                {
                    "role": "assistant",
                    "content": "Result",
                    "product_ids": [True],
                }
            ]
        ),
        json.dumps(
            [
                {
                    "role": "assistant",
                    "content": "Result",
                    "product_ids": ["15"],
                }
            ]
        ),
        json.dumps(
            [
                {
                    "role": "assistant",
                    "content": "Result",
                    "product_ids": [15, 15],
                }
            ]
        ),
        json.dumps(
            [
                {
                    "role": "assistant",
                    "content": "Result",
                    "product_ids": list(range(1, 12)),
                }
            ]
        ),
        json.dumps(
            [
                {
                    "role": "user",
                    "content": "x" * (MAX_STORED_CONTENT_LENGTH + 1),
                }
            ]
        ),
        json.dumps(
            [
                {"role": "user", "content": "Hello"}
                for _ in range(MAX_STORED_MESSAGES + 1)
            ]
        ),
    ],
    ids=[
        "malformed-json",
        "null-top-level",
        "object-top-level",
        "string-top-level",
        "non-object-entry",
        "missing-role",
        "missing-content",
        "unsupported-role",
        "non-text-content",
        "non-list-product-context",
        "zero-product-id",
        "negative-product-id",
        "boolean-product-id",
        "string-product-id",
        "duplicate-product-ids",
        "too-many-product-ids",
        "oversized-content",
        "too-many-messages",
    ],
)
async def test_redis_conversation_rejects_corrupt_payloads(payload: str) -> None:
    redis = AsyncMock()
    redis.get.return_value = payload
    store = RedisConversationStore(redis, ttl_seconds=60)

    with pytest.raises(ConversationCorruptError) as exc_info:
        await store.get("corrupt-conversation")

    assert str(exc_info.value) == "Stored conversation data is invalid"
    redis.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_redis_conversation_accepts_maximum_storage_limits() -> None:
    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        [
            {
                "role": "assistant",
                "content": "x" * MAX_STORED_CONTENT_LENGTH,
                "product_ids": list(range(1, 11)),
            }
            for _ in range(MAX_STORED_MESSAGES)
        ]
    )
    store = RedisConversationStore(redis, ttl_seconds=60)

    messages = await store.get("maximum-conversation")

    assert len(messages) == MAX_STORED_MESSAGES
    assert len(messages[0].content) == MAX_STORED_CONTENT_LENGTH
    assert messages[0].product_ids == tuple(range(1, 11))


@pytest.mark.asyncio
async def test_redis_conversation_refuses_to_save_more_than_maximum_messages() -> None:
    redis = AsyncMock()
    store = RedisConversationStore(redis, ttl_seconds=60)
    messages = [
        ConversationMessage(role="user", content=f"Message {index}")
        for index in range(MAX_STORED_MESSAGES + 1)
    ]

    with pytest.raises(ValueError, match="Conversation history exceeds the storage limit"):
        await store.save("oversized-conversation", messages)

    redis.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_redis_backend_errors_are_not_misreported_as_corrupt_data() -> None:
    redis = AsyncMock()
    redis.get.side_effect = ConnectionError("redis unavailable")
    store = RedisConversationStore(redis, ttl_seconds=60)

    with pytest.raises(ConnectionError, match="redis unavailable"):
        await store.get("conversation-1")

