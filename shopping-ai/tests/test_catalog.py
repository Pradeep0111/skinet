import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import httpx2
import pytest

from app.models import AssistantProduct, CatalogPage
from app.services.catalog import (
    CatalogAccessError,
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


def _product_payloads(product_ids: range) -> list[dict[str, object]]:
    return [{**_product_payload(), "id": product_id} for product_id in product_ids]


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
            payload["data"] = _product_payloads(range(2, 52))
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
        if page_index == 1:
            payload["data"] = _product_payloads(range(1, 51))
        else:
            payload["data"] = [{**_product_payload(), "id": 51}]
        return httpx2.Response(200, json=payload, request=request)

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        products = await client.list_products(max_items=51)
    finally:
        await client.close()

    assert [product.id for product in products] == list(range(1, 52))
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
@pytest.mark.parametrize("status_code", [400, 401, 403, 404])
async def test_catalog_client_normalizes_unsuccessful_endpoint_statuses(
    status_code: int,
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            status_code,
            text="private upstream response",
            request=request,
        )

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        with pytest.raises(CatalogAccessError) as error:
            await client.search_products()
    finally:
        await client.close()

    assert "private upstream response" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [408, 429, 500, 502, 503, 504])
async def test_catalog_client_normalizes_transient_endpoint_statuses(
    status_code: int,
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            status_code,
            text="private upstream response",
            request=request,
        )

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        with pytest.raises(CatalogUnavailableError) as error:
            await client.search_products()
    finally:
        await client.close()

    assert "private upstream response" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "transport_error",
    [
        httpx2.ConnectError("private host detail"),
        httpx2.ConnectTimeout("private timeout detail"),
        httpx2.ReadTimeout("private read detail"),
    ],
)
async def test_catalog_client_normalizes_transport_failures(
    transport_error: httpx2.HTTPError,
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        transport_error.request = request
        raise transport_error

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        with pytest.raises(CatalogUnavailableError) as error:
            await client.search_products()
    finally:
        await client.close()

    assert "private" not in str(error.value)


@pytest.mark.asyncio
async def test_catalog_client_rejects_non_json_success_response() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            content=b"not-json",
            headers={"content-type": "application/json"},
            request=request,
        )

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        with pytest.raises(CatalogContractError):
            await client.search_products(page_size=50)
    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {**_page_payload(), "pageIndex": 2},
        {**_page_payload(), "pageSize": 49},
        {**_page_payload(), "count": 0},
        _page_payload(count=51),
        {
            **_page_payload(count=2),
            "data": [_product_payload(), _product_payload()],
        },
    ],
)
async def test_catalog_client_rejects_inconsistent_pagination(
    payload: dict[str, object],
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=payload, request=request)

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        with pytest.raises(CatalogContractError):
            await client.search_products(page_size=50)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_catalog_client_rejects_early_empty_page() -> None:
    payload = {**_page_payload(count=51), "data": []}

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=payload, request=request)

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        with pytest.raises(CatalogContractError):
            await client.search_products(page_size=50)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_catalog_client_accepts_empty_page_beyond_catalog_count() -> None:
    payload = {
        "pageIndex": 2,
        "pageSize": 50,
        "count": 1,
        "data": [],
    }

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=payload, request=request)

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        page = await client.search_products(page_index=2, page_size=50)
    finally:
        await client.close()

    assert page.data == []


@pytest.mark.asyncio
async def test_catalog_client_accepts_current_dotnet_projection_without_new_optional_fields(
) -> None:
    product = _product_payload()
    product.pop("storageInstructions")
    product.pop("shelfLifeDays")
    payload = {**_page_payload(), "data": [product]}

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=payload, request=request)

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        page = await client.search_products(page_size=50)
    finally:
        await client.close()

    assert page.data[0].storage_instructions is None
    assert page.data[0].shelf_life_days is None


@pytest.mark.asyncio
async def test_catalog_client_rejects_duplicate_products_across_pages() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        page_index = int(request.url.params["pageIndex"])
        payload = _page_payload(page_index=page_index, count=51)
        if page_index == 1:
            payload["data"] = _product_payloads(range(1, 51))
        return httpx2.Response(
            200,
            json=payload,
            request=request,
        )

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        with pytest.raises(CatalogContractError):
            await client.list_products()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_catalog_client_rejects_truncated_complete_snapshot() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "pageIndex": 1,
                "pageSize": 50,
                "count": 51,
                "data": _product_payloads(range(1, 51)),
            },
            request=request,
        )

    client = CatalogClient(
        base_url="https://dotnet.test",
        service_key="catalog-secret",
        timeout_seconds=2,
        transport=httpx2.MockTransport(handler),
    )
    try:
        with pytest.raises(CatalogContractError, match="exceeds"):
            await client.list_products(max_items=50, require_complete=True)
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
    client.list_products.return_value = [product]
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


@pytest.mark.asyncio
async def test_catalog_tools_delegate_search_without_changing_live_detail_client() -> None:
    product = AssistantProduct.model_validate(_product_payload())
    client = AsyncMock(spec=CatalogClient)
    product_search = AsyncMock()
    product_search.search_products.return_value = [product]
    tools = CatalogTools(client, product_search=product_search)

    results = await tools.search_products(
        "fresh fruit",
        max_price=Decimal("5"),
    )

    assert results == [product]
    product_search.search_products.assert_awaited_once()
    assert product_search.search_products.await_args.kwargs["filters"].max_price == Decimal(
        "5"
    )
    client.search_products.assert_not_awaited()


@pytest.mark.asyncio
async def test_keyword_only_search_filters_promotions_by_effective_price() -> None:
    product = AssistantProduct.model_validate(_product_payload())
    client = AsyncMock(spec=CatalogClient)
    client.search_products.return_value = CatalogPage(
        page_index=1,
        page_size=50,
        count=1,
        data=[product],
    )
    client.list_products.return_value = [product]
    tools = CatalogTools(client)

    under_sale_price = await tools.search_products(
        "banana",
        max_price=Decimal("1.50"),
    )
    above_sale_price = await tools.search_products(
        "banana",
        min_price=Decimal("1.50"),
    )

    assert under_sale_price == [product]
    assert above_sale_price == []
    for awaited_call in client.search_products.await_args_list:
        assert awaited_call.kwargs["page_size"] == 50
        assert awaited_call.kwargs["filters"].min_price is None
        assert awaited_call.kwargs["filters"].max_price is None
    client.list_products.assert_awaited_with(
        max_items=1_000,
        require_complete=True,
    )
