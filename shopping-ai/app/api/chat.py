import asyncio
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, status

from app.errors import AssistantAPIError
from app.models import ChatResponse, ErrorResponse, InternalChatRequest
from app.security import require_internal_service_key
from app.services.catalog import (
    CatalogAccessError,
    CatalogContractError,
    CatalogUnavailableError,
    ProductNotFoundError,
)
from app.services.conversation import ConversationCorruptError, ConversationMessage

router = APIRouter(prefix="/api", tags=["internal"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        401: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def internal_chat(
    payload: InternalChatRequest,
    request: Request,
    _: None = Depends(require_internal_service_key),
) -> ChatResponse:
    try:
        async with asyncio.timeout(request.app.state.settings.chat_timeout_seconds):
            return await _process_internal_chat(payload, request)
    except TimeoutError as exc:
        raise AssistantAPIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="assistant_timeout",
            message="The shopping assistant timed out while processing the request.",
            retryable=True,
        ) from exc


async def _process_internal_chat(
    payload: InternalChatRequest,
    request: Request,
) -> ChatResponse:
    settings = request.app.state.settings
    if len(payload.message) > settings.max_message_length:
        raise AssistantAPIError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_code="invalid_request",
            message="The message exceeds the configured maximum length.",
            retryable=False,
        )

    conversation_id = payload.conversation_id or str(uuid4())
    store = request.app.state.conversation_store
    try:
        history = await store.get(conversation_id)
    except ConversationCorruptError:
        history = []
    except TimeoutError:
        raise
    except Exception as exc:
        raise AssistantAPIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="conversation_unavailable",
            message="Conversation history is temporarily unavailable.",
            retryable=True,
        ) from exc

    cart_quantities: dict[int, int] = {}
    if payload.cart is not None:
        for item in payload.cart.items:
            cart_quantities[item.product_id] = (
                cart_quantities.get(item.product_id, 0) + item.quantity
            )

    try:
        result = await request.app.state.shopping_agent.run(
            message=payload.message,
            conversation_id=conversation_id,
            context_product_ids=next(
                (
                    message.product_ids
                    for message in reversed(history)
                    if message.role == "assistant"
                ),
                (),
            ),
            cart_quantities=cart_quantities,
        )
    except ProductNotFoundError:
        result = ChatResponse(
            conversation_id=conversation_id,
            message="I could not find that product in the current catalog.",
            suggested_prompts=["Show me boots"],
        )
    except CatalogUnavailableError as exc:
        raise AssistantAPIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="catalog_unavailable",
            message="The product catalog is temporarily unavailable.",
            retryable=True,
        ) from exc
    except CatalogAccessError as exc:
        raise AssistantAPIError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="catalog_access_error",
            message="The product catalog rejected the assistant request.",
            retryable=False,
        ) from exc
    except CatalogContractError as exc:
        raise AssistantAPIError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="catalog_contract_error",
            message="The product catalog returned an invalid response.",
            retryable=False,
        ) from exc
    response_product_ids = tuple(
        dict.fromkeys(product.id for product in result.products)
    )[:10]
    history_limit = (settings.conversation_max_messages // 2) * 2
    updated_history = [
        *history,
        ConversationMessage(role="user", content=payload.message),
        ConversationMessage(
            role="assistant",
            content=result.message,
            product_ids=response_product_ids,
        ),
    ][-history_limit:]
    try:
        await store.save(conversation_id, updated_history)
    except TimeoutError:
        raise
    except Exception as exc:
        raise AssistantAPIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="conversation_unavailable",
            message="Conversation history could not be saved.",
            retryable=True,
        ) from exc

    return result

