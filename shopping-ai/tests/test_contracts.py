from pathlib import Path

from app.models import AssistantProduct, ChatRequest, ChatResponse, ErrorResponse

FIXTURES = Path(__file__).parent / "fixtures"


def test_product_fixture_matches_contract() -> None:
    payload = (FIXTURES / "assistant_product.json").read_text(encoding="utf-8")
    product = AssistantProduct.model_validate_json(payload)

    assert product.name == "Bananas"
    assert product.quantity_in_stock == 40
    serialized = product.model_dump(by_alias=True, mode="json")
    assert serialized["quantityInStock"] == 40
    assert serialized["price"] == 1.99
    assert isinstance(serialized["price"], float)


def test_chat_response_fixture_allows_confirmation_only_action() -> None:
    payload = (FIXTURES / "chat_response.json").read_text(encoding="utf-8")
    response = ChatResponse.model_validate_json(payload)

    action = response.proposed_actions[0]
    assert action.action_type == "add_to_cart"
    assert action.requires_confirmation is True
    assert action.product_id == response.products[0].id


def test_chat_request_fixture_uses_gateway_contract() -> None:
    payload = (FIXTURES / "chat_request.json").read_text(encoding="utf-8")
    request = ChatRequest.model_validate_json(payload)

    assert request.conversation_id == "conversation-001"
    assert request.cart_id == "cart-001"


def test_error_fixture_uses_safe_public_shape() -> None:
    payload = (FIXTURES / "error_response.json").read_text(encoding="utf-8")
    response = ErrorResponse.model_validate_json(payload)

    assert response.error_code == "assistant_unavailable"
    assert response.retryable is True
