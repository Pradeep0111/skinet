import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.agents import ShoppingAgent
from app.models import AssistantProduct, CatalogPage
from app.services.catalog import CatalogClient
from app.tools import TOOL_ALLOWLIST, CatalogTools

FIXTURES = Path(__file__).parent / "fixtures"


def _products() -> tuple[AssistantProduct, AssistantProduct, AssistantProduct]:
    payload = json.loads(
        (FIXTURES / "assistant_product.json").read_text(encoding="utf-8")
    )
    banana = AssistantProduct.model_validate(payload)
    organic_banana = AssistantProduct.model_validate(
        {
            **payload,
            "id": 2,
            "name": "Organic Bananas",
            "sku": "FRUIT-BANANA-ORGANIC",
            "quantityInStock": 12,
            "promotion": None,
            "effectivePrice": 2.49,
        }
    )
    apple = AssistantProduct.model_validate(
        {
            **payload,
            "id": 3,
            "name": "Apples",
            "sku": "FRUIT-APPLE",
            "quantityInStock": 20,
            "substitutionGroup": "apple",
            "promotion": None,
            "effectivePrice": 3.49,
        }
    )
    return banana, organic_banana, apple


def _agent() -> tuple[ShoppingAgent, AsyncMock]:
    banana, organic_banana, apple = _products()
    by_id = {product.id: product for product in (banana, organic_banana, apple)}
    client = AsyncMock(spec=CatalogClient)

    async def get_product(product_id: int) -> AssistantProduct:
        return by_id[product_id]

    client.get_product.side_effect = get_product
    client.list_products.return_value = [banana, organic_banana, apple]
    client.search_products.return_value = CatalogPage(
        page_index=1,
        page_size=10,
        count=2,
        data=[banana, organic_banana],
    )
    tools = CatalogTools(client, action_id_factory=lambda: "action-test")
    return ShoppingAgent(tools), client


@pytest.mark.asyncio
async def test_agent_routes_keyword_search() -> None:
    agent, client = _agent()

    response = await agent.run(
        message="Show me fresh fruit",
        conversation_id="conversation-1",
    )

    assert [product.id for product in response.products] == [1, 2]
    assert response.comparisons == []
    client.search_products.assert_awaited_once()
    assert client.search_products.await_args.kwargs["query"] == "fresh fruit"


@pytest.mark.asyncio
async def test_agent_routes_comparison_and_returns_structured_result() -> None:
    agent, _ = _agent()

    response = await agent.run(
        message="Compare product 1 and product 2",
        conversation_id="conversation-1",
    )

    assert [product.id for product in response.products] == [1, 2]
    assert response.comparisons[0].product_ids == [1, 2]
    assert "Organic Bananas" in response.comparisons[0].summary


@pytest.mark.asyncio
async def test_agent_routes_substitution_by_catalog_group() -> None:
    agent, _ = _agent()

    response = await agent.run(
        message="Show alternatives to product 1",
        conversation_id="conversation-1",
    )

    assert [product.id for product in response.products] == [2]
    assert "1 in-stock substitute" in response.message


@pytest.mark.asyncio
async def test_agent_routes_details_and_stock_checks() -> None:
    agent, _ = _agent()

    details = await agent.run(
        message="Tell me about product 1",
        conversation_id="conversation-1",
    )
    stock = await agent.run(
        message="Is product 2 available quantity 20?",
        conversation_id="conversation-1",
    )

    assert [product.id for product in details.products] == [1]
    assert "current details" in details.message
    assert [product.id for product in stock.products] == [2]
    assert "not available" in stock.message
    assert "current stock is 12" in stock.message


@pytest.mark.asyncio
async def test_agent_proposes_confirmation_only_action_without_cart_write() -> None:
    agent, client = _agent()

    response = await agent.run(
        message="Add 2 of product 1 to cart",
        conversation_id="conversation-1",
    )

    action = response.proposed_actions[0]
    assert action.action_id == "action-test"
    assert action.action_type == "add_to_cart"
    assert action.quantity == 2
    assert action.requires_confirmation is True
    assert "confirm" in response.message.casefold()
    assert not hasattr(client, "update_cart")


@pytest.mark.asyncio
async def test_agent_does_not_propose_action_when_stock_is_insufficient() -> None:
    agent, _ = _agent()

    response = await agent.run(
        message="Add product 2 to cart quantity 20",
        conversation_id="conversation-1",
    )

    assert response.proposed_actions == []
    assert "Only 12 units" in response.message


@pytest.mark.asyncio
async def test_agent_rejects_out_of_range_quantity_instead_of_clamping_it() -> None:
    agent, client = _agent()

    response = await agent.run(
        message="Add product 1 to cart quantity 100",
        conversation_id="conversation-1",
    )

    assert response.proposed_actions == []
    assert response.message == "Quantity must be between 1 and 99."
    client.get_product.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_requests_ids_before_running_specific_tools() -> None:
    agent, client = _agent()

    response = await agent.run(
        message="Compare these products",
        conversation_id="conversation-1",
    )

    assert response.products == []
    assert "product ID" in response.message
    client.get_product.assert_not_awaited()
    client.search_products.assert_not_awaited()


def test_tool_allowlist_contains_no_mutating_cart_operation() -> None:
    assert TOOL_ALLOWLIST == {
        "search_products",
        "get_product_details",
        "check_stock",
        "compare_products",
        "find_substitutes",
        "propose_add_to_cart",
    }
    assert "add_to_cart" not in TOOL_ALLOWLIST
    assert "update_cart" not in TOOL_ALLOWLIST
