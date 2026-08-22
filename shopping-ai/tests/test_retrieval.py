import json
import sys
from asyncio import gather, sleep
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models import AssistantProduct, CatalogPage
from app.services.catalog import CatalogClient, CatalogFilters, CatalogUnavailableError
from app.services.retrieval import (
    CatalogDocument,
    FaissCatalogIndex,
    HybridProductSearch,
    SemanticSearchUnavailableError,
    SentenceTransformerEmbeddingProvider,
    build_catalog_documents,
    catalog_content_hash,
    reciprocal_rank_fusion,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _product(
    product_id: int,
    name: str,
    description: str,
    *,
    price: str = "10.00",
    stock: int = 10,
) -> AssistantProduct:
    payload = json.loads(
        (FIXTURES / "assistant_product.json").read_text(encoding="utf-8")
    )
    payload.update(
        {
            "id": product_id,
            "name": name,
            "description": description,
            "price": price,
            "effectivePrice": price,
            "quantityInStock": stock,
            "promotion": None,
        }
    )
    return AssistantProduct.model_validate(payload)


class DeterministicEmbeddingProvider:
    model_id = "deterministic-test-v1"

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(tuple(texts))
        vectors: list[list[float]] = []
        for text in texts:
            normalized = text.casefold()
            if any(term in normalized for term in ("head", "hat", "beanie")):
                vectors.append([1.0, 0.0, 0.0])
            elif any(term in normalized for term in ("feet", "boot", "footwear")):
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors


def test_catalog_hash_is_order_independent_and_ignores_live_fields() -> None:
    hat = _product(1, "Warm Hat", "Keeps your head warm", price="12", stock=4)
    boots = _product(2, "Trail Boots", "Outdoor footwear", price="100", stock=8)
    changed_live_values = hat.model_copy(
        update={
            "price": Decimal("99"),
            "effective_price": Decimal("80"),
            "quantity_in_stock": 99,
            "average_rating": Decimal("1"),
            "review_count": 999,
        }
    )

    original = build_catalog_documents([hat, boots])
    reordered = build_catalog_documents([boots, changed_live_values])

    assert catalog_content_hash(original, "model") == catalog_content_hash(
        reordered,
        "model",
    )
    assert catalog_content_hash(original, "model") != catalog_content_hash(
        build_catalog_documents([hat.model_copy(update={"description": "A sun hat"}), boots]),
        "model",
    )


def test_catalog_documents_reject_duplicate_product_ids() -> None:
    hat = _product(1, "Warm Hat", "Keeps your head warm")

    with pytest.raises(SemanticSearchUnavailableError, match="unique"):
        build_catalog_documents([hat, hat])


def test_reciprocal_rank_fusion_is_deterministic_and_deduplicated() -> None:
    assert reciprocal_rank_fusion([1, 2, 2], [2, 3, 3]) == [2, 1, 3]


@pytest.mark.asyncio
async def test_faiss_index_ranks_semantic_match_and_reuses_catalog_embeddings() -> None:
    pytest.importorskip("faiss")
    provider = DeterministicEmbeddingProvider()
    index = FaissCatalogIndex(provider, timeout_seconds=2, minimum_score=0.1)
    products = [
        _product(1, "Warm Hat", "Keeps your head warm"),
        _product(2, "Trail Boots", "Outdoor footwear for your feet"),
    ]

    first = await index.search(products, "something for my head", limit=2)
    second = await index.search(products, "warm beanie", limit=2)

    assert first[0] == 1
    assert second[0] == 1
    assert len(provider.calls) == 3
    assert len(provider.calls[0]) == 2


@pytest.mark.asyncio
async def test_faiss_index_rebuilds_when_semantic_content_changes() -> None:
    pytest.importorskip("faiss")
    provider = DeterministicEmbeddingProvider()
    index = FaissCatalogIndex(provider, timeout_seconds=2, minimum_score=0.1)
    hat = _product(1, "Warm Hat", "Keeps your head warm")

    await index.search([hat], "hat", limit=1)
    await index.search(
        [hat.model_copy(update={"description": "A lightweight sun hat"})],
        "hat",
        limit=1,
    )

    assert len(provider.calls) == 4
    assert all(len(call) == 1 for call in provider.calls)


@pytest.mark.asyncio
async def test_faiss_index_builds_once_for_concurrent_searches() -> None:
    pytest.importorskip("faiss")
    provider = DeterministicEmbeddingProvider()
    index = FaissCatalogIndex(provider, timeout_seconds=2, minimum_score=0.1)
    products = [
        _product(1, "Warm Hat", "Keeps your head warm"),
        _product(2, "Trail Boots", "Outdoor footwear for your feet"),
    ]

    await gather(
        index.search(products, "hat", limit=2),
        index.search(products, "boots", limit=2),
    )

    assert sum(len(call) == 2 for call in provider.calls) == 1


@pytest.mark.asyncio
async def test_faiss_index_rebuilds_invalid_in_memory_snapshot() -> None:
    pytest.importorskip("faiss")
    provider = DeterministicEmbeddingProvider()
    index = FaissCatalogIndex(provider, timeout_seconds=2, minimum_score=0.1)
    products = [_product(1, "Warm Hat", "Keeps your head warm")]

    await index.search(products, "hat", limit=1)
    assert index._snapshot is not None
    index._snapshot = index._snapshot.__class__(
        content_hash=index._snapshot.content_hash,
        product_ids=index._snapshot.product_ids,
        dimension=index._snapshot.dimension,
        index=object(),
    )
    await index.search(products, "hat", limit=1)

    assert sum(len(call) == 1 for call in provider.calls) == 4


@pytest.mark.asyncio
async def test_timed_out_catalog_build_completes_once_in_background() -> None:
    pytest.importorskip("faiss")

    class SlowEmbeddingProvider(DeterministicEmbeddingProvider):
        async def embed(self, texts: Sequence[str]) -> list[list[float]]:
            if len(texts) > 1:
                await sleep(0.05)
            return await super().embed(texts)

    provider = SlowEmbeddingProvider()
    index = FaissCatalogIndex(provider, timeout_seconds=0.01, minimum_score=0.1)
    products = [
        _product(1, "Warm Hat", "Keeps your head warm"),
        _product(2, "Trail Boots", "Outdoor footwear for your feet"),
    ]

    with pytest.raises(SemanticSearchUnavailableError, match="timed out"):
        await index.search(products, "hat", limit=2)
    await sleep(0.08)
    index._timeout_seconds = 1
    assert (await index.search(products, "hat", limit=2))[0] == 1

    assert sum(len(call) == 2 for call in provider.calls) == 1


@pytest.mark.asyncio
async def test_sentence_transformer_provider_loads_lazily(monkeypatch, tmp_path) -> None:
    constructed: list[dict[str, object]] = []

    class FakeVectors:
        def tolist(self) -> list[list[float]]:
            return [[1.0, 0.0]]

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            constructed.append({"model_name": model_name, **kwargs})

        def encode(self, texts: list[str], **kwargs: object) -> FakeVectors:
            assert texts == ["warm hat"]
            assert kwargs["normalize_embeddings"] is True
            return FakeVectors()

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    provider = SentenceTransformerEmbeddingProvider(
        model_name="test-model",
        cache_path=tmp_path,
        revision="test-revision",
        local_files_only=True,
    )

    assert constructed == []
    assert await provider.embed(["warm hat"]) == [[1.0, 0.0]]
    assert constructed[0]["model_name"] == "test-model"
    assert constructed[0]["revision"] == "test-revision"
    assert constructed[0]["local_files_only"] is True
    assert constructed[0]["trust_remote_code"] is False


@pytest.mark.asyncio
async def test_hybrid_search_fuses_ids_and_uses_current_filtered_products() -> None:
    cheap_hat = _product(1, "Warm Hat", "Keeps your head warm", price="12")
    expensive_boots = _product(2, "Trail Boots", "Outdoor footwear", price="220")
    client = AsyncMock(spec=CatalogClient)
    client.search_products.return_value = CatalogPage(
        page_index=1,
        page_size=4,
        count=1,
        data=[cheap_hat],
    )
    client.list_products.return_value = [cheap_hat, expensive_boots]
    semantic_index = AsyncMock(spec=FaissCatalogIndex)
    semantic_index.search.return_value = [2, 1]
    search = HybridProductSearch(client, semantic_index)

    results = await search.search_products(
        "something warm",
        limit=5,
        filters=CatalogFilters(max_price=Decimal("50"), in_stock=True),
    )

    assert results == [cheap_hat]
    client.list_products.assert_awaited_once_with(
        max_items=1_000,
        require_complete=True,
    )


@pytest.mark.asyncio
async def test_hybrid_search_falls_back_to_keyword_on_semantic_failure() -> None:
    hat = _product(1, "Warm Hat", "Keeps your head warm")
    client = AsyncMock(spec=CatalogClient)
    client.search_products.return_value = CatalogPage(
        page_index=1,
        page_size=2,
        count=1,
        data=[hat],
    )
    client.list_products.return_value = [hat]
    semantic_index = AsyncMock(spec=FaissCatalogIndex)
    semantic_index.search.side_effect = SemanticSearchUnavailableError("offline model")
    search = HybridProductSearch(client, semantic_index)

    results = await search.search_products(
        "warm hat",
        limit=1,
        filters=CatalogFilters(in_stock=True),
    )

    assert results == [hat]


@pytest.mark.asyncio
async def test_hybrid_search_falls_back_when_complete_snapshot_fails() -> None:
    hat = _product(1, "Warm Hat", "Keeps your head warm")
    client = AsyncMock(spec=CatalogClient)
    client.search_products.return_value = CatalogPage(
        page_index=1,
        page_size=2,
        count=1,
        data=[hat],
    )
    client.list_products.side_effect = CatalogUnavailableError("catalog page failed")
    semantic_index = AsyncMock(spec=FaissCatalogIndex)
    search = HybridProductSearch(client, semantic_index)

    results = await search.search_products(
        "warm hat",
        limit=1,
        filters=CatalogFilters(in_stock=True),
    )

    assert results == [hat]
    semantic_index.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_hybrid_budget_uses_effective_price_during_fallback() -> None:
    promoted_hat = _product(1, "Warm Hat", "Keeps your head warm", price="20")
    promoted_hat = promoted_hat.model_copy(update={"effective_price": Decimal("9")})
    client = AsyncMock(spec=CatalogClient)
    client.search_products.return_value = CatalogPage(
        page_index=1,
        page_size=2,
        count=1,
        data=[promoted_hat],
    )
    client.list_products.side_effect = CatalogUnavailableError("snapshot failed")
    semantic_index = AsyncMock(spec=FaissCatalogIndex)
    search = HybridProductSearch(client, semantic_index)

    results = await search.search_products(
        "warm hat",
        limit=1,
        filters=CatalogFilters(max_price=Decimal("10"), in_stock=True),
    )

    assert results == [promoted_hat]
    upstream_filters = client.search_products.await_args.kwargs["filters"]
    assert upstream_filters.max_price is None


@pytest.mark.asyncio
async def test_hybrid_drops_keyword_product_missing_from_current_snapshot() -> None:
    deleted_hat = _product(1, "Warm Hat", "Keeps your head warm")
    current_boots = _product(2, "Trail Boots", "Outdoor footwear")
    client = AsyncMock(spec=CatalogClient)
    client.search_products.return_value = CatalogPage(
        page_index=1,
        page_size=2,
        count=1,
        data=[deleted_hat],
    )
    client.list_products.return_value = [current_boots]
    semantic_index = AsyncMock(spec=FaissCatalogIndex)
    semantic_index.search.return_value = []
    search = HybridProductSearch(client, semantic_index)

    results = await search.search_products(
        "warm hat",
        limit=1,
        filters=CatalogFilters(in_stock=True),
    )

    assert results == []


@pytest.mark.asyncio
async def test_semantic_fallback_uses_current_snapshot_not_stale_keyword_item() -> None:
    stale_hat = _product(1, "Warm Hat", "Keeps your head warm", price="12", stock=10)
    current_hat = stale_hat.model_copy(
        update={"effective_price": Decimal("9"), "quantity_in_stock": 2}
    )
    client = AsyncMock(spec=CatalogClient)
    client.search_products.return_value = CatalogPage(
        page_index=1,
        page_size=2,
        count=1,
        data=[stale_hat],
    )
    client.list_products.return_value = [current_hat]
    semantic_index = AsyncMock(spec=FaissCatalogIndex)
    semantic_index.search.side_effect = SemanticSearchUnavailableError("model failed")
    search = HybridProductSearch(client, semantic_index)

    results = await search.search_products(
        "warm hat",
        limit=1,
        filters=CatalogFilters(in_stock=True),
    )

    assert results == [current_hat]
    assert results[0].effective_price == Decimal("9")
    assert results[0].quantity_in_stock == 2


@pytest.mark.asyncio
async def test_semantic_fallback_finds_budget_match_after_first_keyword_page() -> None:
    expensive = [
        _product(index, f"Trail Boots {index:02}", "Outdoor footwear", price="200")
        for index in range(1, 51)
    ]
    affordable = _product(51, "Trail Boots 51", "Outdoor footwear", price="50")
    client = AsyncMock(spec=CatalogClient)
    client.search_products.return_value = CatalogPage(
        page_index=1,
        page_size=50,
        count=51,
        data=expensive,
    )
    client.list_products.return_value = [*expensive, affordable]
    semantic_index = AsyncMock(spec=FaissCatalogIndex)
    semantic_index.search.side_effect = SemanticSearchUnavailableError("model failed")
    search = HybridProductSearch(client, semantic_index)

    results = await search.search_products(
        "trail boots",
        limit=10,
        filters=CatalogFilters(max_price=Decimal("100"), in_stock=True),
    )

    assert results == [affordable]


@pytest.mark.asyncio
async def test_hybrid_search_preserves_primary_keyword_catalog_error() -> None:
    client = AsyncMock(spec=CatalogClient)
    client.search_products.side_effect = CatalogUnavailableError("catalog offline")
    client.list_products.return_value = []
    semantic_index = AsyncMock(spec=FaissCatalogIndex)
    search = HybridProductSearch(client, semantic_index)

    with pytest.raises(CatalogUnavailableError):
        await search.search_products(
            "hat",
            limit=1,
            filters=CatalogFilters(in_stock=True),
        )


def test_content_hash_includes_model_identity() -> None:
    documents = (CatalogDocument(product_id=1, text="name: warm hat"),)

    assert catalog_content_hash(documents, "model-a") != catalog_content_hash(
        documents,
        "model-b",
    )
