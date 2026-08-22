import asyncio
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

from app.models import AssistantProduct, ProductComparison, ProposedAction, StockCheck
from app.services.catalog import CatalogClient, CatalogClientError, CatalogFilters
from app.services.retrieval import (
    ProductSearch,
    keyword_ranked_products,
    matches_catalog_filters,
)

TOOL_ALLOWLIST = frozenset(
    {
        "search_products",
        "get_product_details",
        "check_stock",
        "compare_products",
        "find_substitutes",
        "propose_add_to_cart",
    }
)


class InsufficientStockError(ValueError):
    """A proposed action asks for more stock than the catalog currently has."""


class CatalogTools:
    """Typed read-only operations that can be allowlisted by the Week 4 agent."""

    def __init__(
        self,
        client: CatalogClient,
        *,
        action_id_factory: Callable[[], str] | None = None,
        product_search: ProductSearch | None = None,
    ) -> None:
        self._client = client
        self._action_id_factory = action_id_factory or (lambda: str(uuid4()))
        self._product_search = product_search

    async def search_products(
        self,
        keyword: str,
        *,
        limit: int = 10,
        category: str | None = None,
        dietary_labels: tuple[str, ...] = (),
        allergens_excluded: tuple[str, ...] = (),
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        in_stock: bool = True,
    ) -> list[AssistantProduct]:
        normalized_keyword = keyword.strip()
        if not normalized_keyword:
            raise ValueError("keyword cannot be empty")
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise ValueError("min_price cannot exceed max_price")

        filters = CatalogFilters(
            categories=(category,) if category else (),
            dietary_labels=dietary_labels,
            allergens_excluded=allergens_excluded,
            min_price=min_price,
            max_price=max_price,
            in_stock=in_stock,
        )
        if self._product_search is not None:
            return await self._product_search.search_products(
                normalized_keyword,
                limit=limit,
                filters=filters,
            )
        upstream_filters = replace(filters, min_price=None, max_price=None)
        page = await self._client.search_products(
            query=normalized_keyword,
            page_size=(
                50
                if filters.min_price is not None or filters.max_price is not None
                else limit
            ),
            filters=upstream_filters,
        )
        page_products = [
            product for product in page.data if matches_catalog_filters(product, filters)
        ]
        if filters.min_price is None and filters.max_price is None:
            return page_products[:limit]
        try:
            catalog = await self._client.list_products(
                max_items=1_000,
                require_complete=True,
            )
        except CatalogClientError:
            return page_products[:limit]
        return keyword_ranked_products(catalog, normalized_keyword, filters)[:limit]

    async def get_product_details(self, product_id: int) -> AssistantProduct:
        return await self._client.get_product(product_id)

    async def check_stock(
        self,
        product_id: int,
        *,
        requested_quantity: int = 1,
    ) -> StockCheck:
        if not 1 <= requested_quantity <= 99:
            raise ValueError("requested_quantity must be between 1 and 99")
        product = await self._client.get_product(product_id)
        return StockCheck(
            product_id=product.id,
            requested_quantity=requested_quantity,
            quantity_in_stock=product.quantity_in_stock,
            available=product.quantity_in_stock >= requested_quantity,
        )

    async def compare_products(
        self,
        product_ids: tuple[int, ...],
    ) -> tuple[list[AssistantProduct], ProductComparison]:
        if not 2 <= len(product_ids) <= 4:
            raise ValueError("compare_products requires between 2 and 4 product IDs")
        if len(set(product_ids)) != len(product_ids):
            raise ValueError("product IDs must be unique")

        products = list(
            await asyncio.gather(
                *(self._client.get_product(product_id) for product_id in product_ids)
            )
        )
        summary = "; ".join(
            f"{product.name}: price {product.effective_price}, "
            f"{product.quantity_in_stock} in stock"
            for product in products
        )
        comparison = ProductComparison(
            title="Product comparison",
            product_ids=[product.id for product in products],
            summary=summary,
        )
        return products, comparison

    async def find_substitutes(
        self,
        product_id: int,
        *,
        limit: int = 5,
    ) -> list[AssistantProduct]:
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        product = await self._client.get_product(product_id)
        if not product.substitution_group:
            return []

        group = product.substitution_group.casefold()
        catalog = await self._client.list_products(max_items=500)
        return [
            candidate
            for candidate in catalog
            if candidate.id != product.id
            and candidate.quantity_in_stock > 0
            and candidate.substitution_group
            and candidate.substitution_group.casefold() == group
        ][:limit]

    async def propose_add_to_cart(
        self,
        product_id: int,
        *,
        quantity: int = 1,
        existing_quantity: int = 0,
    ) -> tuple[AssistantProduct, ProposedAction]:
        if not 1 <= quantity <= 99:
            raise ValueError("quantity must be between 1 and 99")
        if type(existing_quantity) is not int or existing_quantity < 0:
            raise ValueError("existing_quantity must be a non-negative integer")
        product = await self._client.get_product(product_id)
        requested_total = existing_quantity + quantity
        if product.quantity_in_stock < requested_total:
            cart_context = (
                f", and {existing_quantity} are already in your cart"
                if existing_quantity
                else ""
            )
            raise InsufficientStockError(
                f"Only {product.quantity_in_stock} units are currently available{cart_context}."
            )

        action = ProposedAction(
            action_id=self._action_id_factory(),
            action_type="add_to_cart",
            product_id=product.id,
            quantity=quantity,
            label=f"Add {quantity} × {product.name} to cart",
            requires_confirmation=True,
        )
        return product, action
