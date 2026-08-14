import json
from unittest.mock import AsyncMock

import pytest

from app.services.conversation import (
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

