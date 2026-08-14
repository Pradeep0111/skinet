import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import httpx2
import pytest

from app.models import AssistantProduct, CatalogPage
from app.services.catalog import (
    CatalogClient,
    CatalogContractError,
    CatalogFilters,
    CatalogUnavailableError,
    ProductNotFoundError,
)
from app.tools import CatalogTools

FIXTURES = Path(__file__).parent / "fixtures"


def _product_payload() -> dict[str, object]:
    return json.loads((FIXTURES / "assistant_product.json").read_text(encoding="utf-8"))


def _page_payload(*, page_index: int = 1, count: int = 1) -> dict[str, object]:
    return {
        "pageIndex": page_index,
        "pageSize": 50,
        "count": count,
        "data": [_product_payload()],
    }


@pytest.mark.asyncio
async def test_catalog_client_sends_service_key_filters_and_parses_contract() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/api/assistant/catalog"
        assert request.headers["X-Assistant-Service-Key"] == "catalog-secret"
        assert request.url.params["search"] == "fresh fruit"
        assert request.url.params["pageIndex"] == "1"
        assert request.url.params["pageSize"] == "50"
        assert request.url.params["categories"] == "Groceries,Fruit"
        assert request.url.params["dietaryLabels"] == "vegan"
        assert request.url.params["allergensExcluded"] == "nuts"
        assert request.url.params["maxPrice"] == "500"
        assert request.url.params["inStock"] == "true"
        return httpx2.Response(200, json=_page_payload(), request=request)

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        page = await client.search_products(
            query=" fresh fruit ",
            page_size=50,
            filters=CatalogFilters(
                categories=("Groceries", "Fruit"),
                dietary_labels=("vegan",),
                allergens_excluded=("nuts",),
                max_price=Decimal("500"),
                in_stock=True,
            ),
        )
    finally:
        await client.close()

    assert page.data[0].name == "Bananas"
    assert page.data[0].quantity_in_stock == 40


@pytest.mark.asyncio
async def test_catalog_client_paginates_for_exact_product_lookup() -> None:
    requested_pages: list[int] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        page_index = int(request.url.params["pageIndex"])
        requested_pages.append(page_index)
        payload = _page_payload(page_index=page_index, count=51)
        if page_index == 1:
            payload["data"] = [{**_product_payload(), "id": 2}]
        return httpx2.Response(200, json=payload, request=request)

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        product = await client.get_product(1)
    finally:
        await client.close()

    assert product.name == "Bananas"
    assert requested_pages == [1, 2]


@pytest.mark.asyncio
async def test_catalog_client_lists_products_across_bounded_pages() -> None:
    requested_pages: list[int] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        page_index = int(request.url.params["pageIndex"])
        requested_pages.append(page_index)
        payload = _page_payload(page_index=page_index, count=51)
        payload["data"] = [{**_product_payload(), "id": page_index}]
        return httpx2.Response(200, json=payload, request=request)

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        products = await client.list_products(max_items=10)
    finally:
        await client.close()

    assert [product.id for product in products] == [1, 2]
    assert requested_pages == [1, 2]


@pytest.mark.asyncio
async def test_catalog_client_reports_missing_product() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=_page_payload(), request=request)

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        with pytest.raises(ProductNotFoundError):
            await client.get_product(999)
    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected_error"),
    [
        (httpx2.Response(503), CatalogUnavailableError),
        (httpx2.Response(200, json={"unexpected": True}), CatalogContractError),
    ],
)
async def test_catalog_client_normalizes_remote_and_contract_failures(
    response: httpx2.Response,
    expected_error: type[Exception],
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        response.request = request
        return response

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        with pytest.raises(expected_error):
            await client.search_products()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_catalog_tools_are_read_only_and_return_current_stock() -> None:
    product = AssistantProduct.model_validate(_product_payload())
    client = AsyncMock()
    client.search_products.return_value = CatalogPage(
        page_index=1,
        page_size=10,
        count=1,
        data=[product],
    )
    client.get_product.return_value = product
    tools = CatalogTools(client)

    results = await tools.search_products(
        "banana",
        category="Groceries",
        dietary_labels=("vegan",),
        max_price=Decimal("500"),
    )
    stock = await tools.check_stock(1, requested_quantity=20)

    assert results == [product]
    assert stock.available is True
    assert stock.quantity_in_stock == 40
    assert not hasattr(tools, "add_to_cart")
