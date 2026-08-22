import asyncio
import hashlib
import json
import logging
import re
import threading
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from app.models import AssistantProduct
from app.services.catalog import CatalogClient, CatalogFilters

logger = logging.getLogger(__name__)

_DOCUMENT_SCHEMA_VERSION = 1
_RRF_K = 60
_WHITESPACE = re.compile(r"\s+")


class SemanticSearchUnavailableError(RuntimeError):
    """Semantic retrieval failed and callers should use keyword results."""


class EmbeddingProvider(Protocol):
    @property
    def model_id(self) -> str: ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class ProductSearch(Protocol):
    async def search_products(
        self,
        keyword: str,
        *,
        limit: int,
        filters: CatalogFilters,
    ) -> list[AssistantProduct]: ...


@dataclass(frozen=True, slots=True)
class CatalogDocument:
    product_id: int
    text: str


@dataclass(frozen=True, slots=True)
class _IndexSnapshot:
    content_hash: str
    product_ids: tuple[int, ...]
    dimension: int
    index: Any


class SentenceTransformerEmbeddingProvider:
    """Lazy local embedding provider that never blocks the async event loop."""

    def __init__(
        self,
        *,
        model_name: str,
        cache_path: Path,
        revision: str | None = None,
        local_files_only: bool = False,
    ) -> None:
        self._model_name = model_name
        self._cache_path = cache_path
        self._revision = revision
        self._local_files_only = local_files_only
        self._model: Any | None = None
        self._inference_lock = asyncio.Lock()
        self._model_lock = threading.Lock()

    @property
    def model_id(self) -> str:
        return f"{self._model_name}@{self._revision or 'default'}"

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        async with self._inference_lock:
            try:
                return await asyncio.to_thread(self._encode, list(texts))
            except SemanticSearchUnavailableError:
                raise
            except Exception as exc:
                raise SemanticSearchUnavailableError(
                    "The embedding model could not encode the catalog."
                ) from exc

    def _encode(self, texts: list[str]) -> list[list[float]]:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise SemanticSearchUnavailableError(
                "Install the semantic dependency extra to enable embeddings."
            ) from exc

        with self._model_lock:
            if self._model is None:
                self._cache_path.mkdir(parents=True, exist_ok=True)
                self._model = SentenceTransformer(
                    self._model_name,
                    cache_folder=str(self._cache_path),
                    revision=self._revision,
                    local_files_only=self._local_files_only,
                    trust_remote_code=False,
                )
            vectors = self._model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        return vectors.tolist()


class FaissCatalogIndex:
    """Lazily rebuilt in-memory cosine index containing only product IDs."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        *,
        timeout_seconds: float,
        minimum_score: float = 0.20,
    ) -> None:
        if not -1 <= minimum_score <= 1:
            raise ValueError("minimum_score must be between -1 and 1")
        self._embedding_provider = embedding_provider
        self._timeout_seconds = timeout_seconds
        self._minimum_score = minimum_score
        self._snapshot: _IndexSnapshot | None = None
        self._rebuild_lock = asyncio.Lock()
        self._build_task: asyncio.Task[_IndexSnapshot] | None = None
        self._build_hash: str | None = None

    async def search(
        self,
        products: Sequence[AssistantProduct],
        query: str,
        *,
        limit: int,
    ) -> list[int]:
        documents = build_catalog_documents(products)
        if not documents or not query.strip():
            return []
        ensure_task = asyncio.create_task(self._ensure_snapshot(documents))
        try:
            async with asyncio.timeout(self._timeout_seconds):
                snapshot = await asyncio.shield(ensure_task)
                query_vectors = await self._embedding_provider.embed([query])
                return await asyncio.to_thread(
                    self._search_sync,
                    snapshot,
                    query_vectors,
                    limit,
                )
        except TimeoutError as exc:
            ensure_task.add_done_callback(_consume_background_result)
            raise SemanticSearchUnavailableError("Semantic search timed out.") from exc
        except SemanticSearchUnavailableError:
            raise
        except asyncio.CancelledError:
            ensure_task.add_done_callback(_consume_background_result)
            raise
        except Exception as exc:
            raise SemanticSearchUnavailableError("Semantic search failed.") from exc

    async def _ensure_snapshot(
        self,
        documents: Sequence[CatalogDocument],
    ) -> _IndexSnapshot:
        content_hash = catalog_content_hash(documents, self._embedding_provider.model_id)
        if self._snapshot_is_valid(self._snapshot, documents, content_hash):
            assert self._snapshot is not None
            return self._snapshot

        async with self._rebuild_lock:
            if self._snapshot_is_valid(self._snapshot, documents, content_hash):
                assert self._snapshot is not None
                return self._snapshot
            if (
                self._build_task is None
                or self._build_hash != content_hash
            ):
                self._build_hash = content_hash
                self._build_task = asyncio.create_task(
                    self._build_snapshot(documents, content_hash)
                )
            build_task = self._build_task

        try:
            snapshot = await asyncio.shield(build_task)
        except BaseException:
            async with self._rebuild_lock:
                if self._build_task is build_task:
                    self._build_task = None
                    self._build_hash = None
            raise

        async with self._rebuild_lock:
            if self._build_task is build_task:
                self._snapshot = snapshot
                self._build_task = None
                self._build_hash = None
        return snapshot

    async def _build_snapshot(
        self,
        documents: Sequence[CatalogDocument],
        content_hash: str,
    ) -> _IndexSnapshot:
        vectors = await self._embedding_provider.embed(
            [document.text for document in documents]
        )
        return await asyncio.to_thread(
            self._build_sync,
            documents,
            vectors,
            content_hash,
        )

    @staticmethod
    def _snapshot_is_valid(
        snapshot: _IndexSnapshot | None,
        documents: Sequence[CatalogDocument],
        content_hash: str,
    ) -> bool:
        if snapshot is None:
            return False
        product_ids = tuple(document.product_id for document in documents)
        try:
            return (
                snapshot.content_hash == content_hash
                and snapshot.product_ids == product_ids
                and snapshot.dimension > 0
                and snapshot.index.d == snapshot.dimension
                and snapshot.index.ntotal == len(product_ids)
            )
        except (AttributeError, TypeError, ValueError):
            return False

    @staticmethod
    def _dependencies() -> tuple[Any, Any]:
        try:
            import faiss
            import numpy
        except ImportError as exc:
            raise SemanticSearchUnavailableError(
                "Install the semantic dependency extra to enable FAISS."
            ) from exc
        return faiss, numpy

    @classmethod
    def _build_sync(
        cls,
        documents: Sequence[CatalogDocument],
        vectors: Sequence[Sequence[float]],
        content_hash: str,
    ) -> _IndexSnapshot:
        faiss, numpy = cls._dependencies()
        matrix = numpy.asarray(vectors, dtype="float32")
        if matrix.ndim != 2 or matrix.shape[0] != len(documents) or matrix.shape[1] < 1:
            raise SemanticSearchUnavailableError("Embedding output has an invalid shape.")
        if not numpy.isfinite(matrix).all():
            raise SemanticSearchUnavailableError("Embedding output contains invalid values.")
        norms = numpy.linalg.norm(matrix, axis=1, keepdims=True)
        if numpy.any(norms <= 0):
            raise SemanticSearchUnavailableError("Embedding output contains zero vectors.")
        matrix = numpy.ascontiguousarray(matrix / norms, dtype="float32")
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)
        return _IndexSnapshot(
            content_hash=content_hash,
            product_ids=tuple(document.product_id for document in documents),
            dimension=matrix.shape[1],
            index=index,
        )

    def _search_sync(
        self,
        snapshot: _IndexSnapshot,
        vectors: Sequence[Sequence[float]],
        limit: int,
    ) -> list[int]:
        _, numpy = self._dependencies()
        matrix = numpy.asarray(vectors, dtype="float32")
        if matrix.shape != (1, snapshot.dimension) or not numpy.isfinite(matrix).all():
            raise SemanticSearchUnavailableError("Query embedding has an invalid shape.")
        norm = numpy.linalg.norm(matrix, axis=1, keepdims=True)
        if numpy.any(norm <= 0):
            raise SemanticSearchUnavailableError("Query embedding is empty.")
        matrix = numpy.ascontiguousarray(matrix / norm, dtype="float32")
        scores, positions = snapshot.index.search(
            matrix,
            min(limit, len(snapshot.product_ids)),
        )
        return [
            snapshot.product_ids[position]
            for score, position in zip(scores[0], positions[0], strict=True)
            if position >= 0 and float(score) >= self._minimum_score
        ]


class HybridProductSearch:
    """Fuses live .NET keyword results with semantic product-ID rankings."""

    def __init__(
        self,
        client: CatalogClient,
        semantic_index: FaissCatalogIndex,
        *,
        max_catalog_items: int = 1_000,
    ) -> None:
        self._client = client
        self._semantic_index = semantic_index
        self._max_catalog_items = max_catalog_items

    async def search_products(
        self,
        keyword: str,
        *,
        limit: int,
        filters: CatalogFilters,
    ) -> list[AssistantProduct]:
        keyword_filters = replace(filters, min_price=None, max_price=None)
        keyword_page_size = (
            50
            if filters.min_price is not None or filters.max_price is not None
            else min(50, max(limit * 2, limit))
        )
        keyword_result, catalog_result = await asyncio.gather(
            self._client.search_products(
                query=keyword,
                page_size=keyword_page_size,
                filters=keyword_filters,
            ),
            self._client.list_products(
                max_items=self._max_catalog_items,
                require_complete=True,
            ),
            return_exceptions=True,
        )
        if isinstance(keyword_result, BaseException):
            raise keyword_result
        endpoint_keyword_products = [
            product
            for product in keyword_result.data
            if matches_catalog_filters(product, filters)
        ]
        if isinstance(catalog_result, BaseException):
            logger.warning(
                "semantic_catalog_snapshot_failed error_type=%s",
                type(catalog_result).__name__,
            )
            return endpoint_keyword_products[:limit]

        current_products = {
            product.id: product
            for product in catalog_result
            if matches_catalog_filters(product, filters)
        }
        local_keyword_ids = [
            product.id
            for product in keyword_ranked_products(
                current_products.values(),
                keyword,
                filters,
            )
        ]
        endpoint_keyword_ids = [
            product.id
            for product in endpoint_keyword_products
            if product.id in current_products
        ]
        keyword_ids = list(dict.fromkeys([*endpoint_keyword_ids, *local_keyword_ids]))
        try:
            semantic_ids = await self._semantic_index.search(
                catalog_result,
                keyword,
                limit=len(catalog_result),
            )
        except SemanticSearchUnavailableError as exc:
            logger.warning(
                "semantic_search_fallback error_type=%s",
                type(exc.__cause__ or exc).__name__,
            )
            return [current_products[product_id] for product_id in keyword_ids[:limit]]

        semantic_ids = [product_id for product_id in semantic_ids if product_id in current_products]
        ranked_ids = reciprocal_rank_fusion(keyword_ids, semantic_ids)
        return [current_products[product_id] for product_id in ranked_ids[:limit]]


def build_catalog_documents(
    products: Sequence[AssistantProduct],
) -> tuple[CatalogDocument, ...]:
    if len({product.id for product in products}) != len(products):
        raise SemanticSearchUnavailableError("Catalog products must have unique IDs.")
    return tuple(
        CatalogDocument(product_id=product.id, text=_product_document(product))
        for product in sorted(products, key=lambda item: item.id)
    )


def catalog_content_hash(
    documents: Sequence[CatalogDocument],
    model_id: str,
) -> str:
    payload = {
        "schemaVersion": _DOCUMENT_SCHEMA_VERSION,
        "modelId": model_id,
        "documents": [
            {"productId": document.product_id, "text": document.text}
            for document in documents
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def reciprocal_rank_fusion(
    keyword_ids: Sequence[int],
    semantic_ids: Sequence[int],
) -> list[int]:
    keyword_rank = _first_ranks(keyword_ids)
    semantic_rank = _first_ranks(semantic_ids)
    product_ids = set(keyword_rank) | set(semantic_rank)

    def sort_key(product_id: int) -> tuple[float, int, int, int]:
        score = sum(
            1 / (_RRF_K + rank)
            for rank in (keyword_rank.get(product_id), semantic_rank.get(product_id))
            if rank is not None
        )
        return (
            -score,
            keyword_rank.get(product_id, 1_000_000),
            semantic_rank.get(product_id, 1_000_000),
            product_id,
        )

    return sorted(product_ids, key=sort_key)


def _first_ranks(product_ids: Sequence[int]) -> dict[int, int]:
    ranks: dict[int, int] = {}
    for rank, product_id in enumerate(product_ids, 1):
        ranks.setdefault(product_id, rank)
    return ranks


def _consume_background_result(task: asyncio.Task[_IndexSnapshot]) -> None:
    try:
        task.result()
    except BaseException:
        pass


def _product_document(product: AssistantProduct) -> str:
    nutrition = (
        json.dumps(
            product.nutrition.model_dump(mode="json", exclude_none=True),
            sort_keys=True,
            separators=(",", ":"),
        )
        if product.nutrition is not None
        else ""
    )
    fields: tuple[tuple[str, object], ...] = (
        ("name", product.name),
        ("description", product.description),
        ("brand", product.brand),
        ("type", product.type),
        ("category", product.category or ""),
        ("subcategory", product.subcategory or ""),
        ("sku", product.sku or ""),
        (
            "unit",
            " ".join(
                str(value)
                for value in (product.unit_size, product.unit_label)
                if value
            ),
        ),
        ("tags", " ".join(sorted(product.tags, key=str.casefold))),
        ("dietary", " ".join(sorted(product.dietary_labels, key=str.casefold))),
        ("allergens", " ".join(sorted(product.allergens, key=str.casefold))),
        ("ingredients", product.ingredients or ""),
        ("nutrition", nutrition),
        ("origin", product.origin or ""),
        ("storage", product.storage_instructions or ""),
        ("shelf life days", product.shelf_life_days if product.shelf_life_days is not None else ""),
        ("substitution group", product.substitution_group or ""),
    )
    return "\n".join(
        f"{label}: {_normalize_text(str(value))}"
        for label, value in fields
        if str(value).strip()
    )


def _normalize_text(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip().casefold()


def matches_catalog_filters(product: AssistantProduct, filters: CatalogFilters) -> bool:
    if filters.in_stock is True and product.quantity_in_stock <= 0:
        return False
    if filters.in_stock is False and product.quantity_in_stock > 0:
        return False
    if filters.min_price is not None and product.effective_price < filters.min_price:
        return False
    if filters.max_price is not None and product.effective_price > filters.max_price:
        return False
    if filters.categories:
        category = (product.category or "").casefold()
        if category not in {value.casefold() for value in filters.categories}:
            return False
    labels = {value.casefold() for value in product.dietary_labels}
    if any(value.casefold() not in labels for value in filters.dietary_labels):
        return False
    allergens = {value.casefold() for value in product.allergens}
    if any(value.casefold() in allergens for value in filters.allergens_excluded):
        return False
    return True


def keyword_ranked_products(
    products: Sequence[AssistantProduct],
    keyword: str,
    filters: CatalogFilters,
) -> list[AssistantProduct]:
    normalized_keyword = keyword.strip().casefold()
    return sorted(
        (
            product
            for product in products
            if normalized_keyword in product.name.casefold()
            and matches_catalog_filters(product, filters)
        ),
        key=lambda product: (product.name.casefold(), product.id),
    )
