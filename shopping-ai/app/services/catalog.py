from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx2
from pydantic import ValidationError

from app.config import Settings
from app.models import AssistantProduct, CatalogPage

CATALOG_PATH = "/api/assistant/catalog"
SERVICE_KEY_HEADER = "X-Assistant-Service-Key"


class CatalogClientError(RuntimeError):
    """Base error raised at the .NET catalog boundary."""


class CatalogUnavailableError(CatalogClientError):
    """The catalog could not be reached or returned an unsuccessful response."""


class CatalogContractError(CatalogClientError):
    """The catalog response did not match the shared contract."""


class ProductNotFoundError(CatalogClientError):
    """The requested product is not present in the catalog projection."""


@dataclass(frozen=True, slots=True)
class CatalogFilters:
    categories: tuple[str, ...] = ()
    dietary_labels: tuple[str, ...] = ()
    allergens_excluded: tuple[str, ...] = ()
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock: bool | None = None


class CatalogClient:
    """Async, read-only client for the service-authenticated ASP.NET catalog."""

    def __init__(
        self,
        *,
        base_url: str,
        service_key: str | None,
        timeout_seconds: float,
        verify_tls: bool = True,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        headers = {SERVICE_KEY_HEADER: service_key} if service_key else {}
        self._client = httpx2.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout_seconds,
            verify=verify_tls,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def search_products(
        self,
        *,
        query: str | None = None,
        page_index: int = 1,
        page_size: int = 20,
        filters: CatalogFilters | None = None,
    ) -> CatalogPage:
        if page_index < 1:
            raise ValueError("page_index must be at least 1")
        if not 1 <= page_size <= 50:
            raise ValueError("page_size must be between 1 and 50")

        params: dict[str, Any] = {"pageIndex": page_index, "pageSize": page_size}
        if query and query.strip():
            params["search"] = query.strip()
        self._add_filters(params, filters or CatalogFilters())

        try:
            response = await self._client.get(CATALOG_PATH, params=params)
            response.raise_for_status()
        except httpx2.HTTPError as exc:
            raise CatalogUnavailableError("The .NET catalog is unavailable.") from exc

        try:
            return CatalogPage.model_validate(response.json())
        except (ValidationError, ValueError) as exc:
            raise CatalogContractError(
                "The .NET catalog response does not match the shared contract."
            ) from exc

    async def get_product(self, product_id: int) -> AssistantProduct:
        if product_id < 1:
            raise ValueError("product_id must be positive")

        page = await self.search_products(page_index=1, page_size=50)
        while True:
            product = next((item for item in page.data if item.id == product_id), None)
            if product is not None:
                return product
            if page.page_index * page.page_size >= page.count:
                raise ProductNotFoundError(f"Product {product_id} was not found.")
            page = await self.search_products(
                page_index=page.page_index + 1,
                page_size=page.page_size,
            )

    async def list_products(self, *, max_items: int = 500) -> list[AssistantProduct]:
        if not 1 <= max_items <= 1_000:
            raise ValueError("max_items must be between 1 and 1000")

        products: list[AssistantProduct] = []
        page_index = 1
        while len(products) < max_items:
            page = await self.search_products(page_index=page_index, page_size=50)
            products.extend(page.data[: max_items - len(products)])
            if page.page_index * page.page_size >= page.count or not page.data:
                break
            page_index += 1
        return products

    @staticmethod
    def _add_filters(params: dict[str, Any], filters: CatalogFilters) -> None:
        if filters.categories:
            params["categories"] = ",".join(filters.categories)
        if filters.dietary_labels:
            params["dietaryLabels"] = ",".join(filters.dietary_labels)
        if filters.allergens_excluded:
            params["allergensExcluded"] = ",".join(filters.allergens_excluded)
        if filters.min_price is not None:
            params["minPrice"] = str(filters.min_price)
        if filters.max_price is not None:
            params["maxPrice"] = str(filters.max_price)
        if filters.in_stock is not None:
            params["inStock"] = str(filters.in_stock).lower()


def create_catalog_client(settings: Settings) -> CatalogClient:
    service_key = (
        settings.dotnet_service_key.get_secret_value()
        if settings.dotnet_service_key is not None
        else None
    )
    return CatalogClient(
        base_url=str(settings.dotnet_base_url),
        service_key=service_key,
        timeout_seconds=settings.request_timeout_seconds,
        verify_tls=settings.dotnet_verify_tls,
    )
