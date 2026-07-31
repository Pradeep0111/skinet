from uuid import uuid4

from fastapi import APIRouter, Depends, Request, status

from app.errors import AssistantAPIError
from app.models import ChatResponse, ErrorResponse, InternalChatRequest
from app.security import require_internal_service_key
from app.services.llm import LLMMessage, LLMProviderError

router = APIRouter(prefix="/internal", tags=["internal"])

SYSTEM_PROMPT = """You are Skinet's shopping assistant.
Use only Skinet catalog information supplied by approved tools.
Never claim that you changed a cart, placed an order, made a payment, or completed an admin action.
Until catalog tools are connected, answer briefly and ask a useful shopping clarification.
"""


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def internal_chat(
    payload: InternalChatRequest,
    request: Request,
    _: None = Depends(require_internal_service_key),
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
    except Exception as exc:
        raise AssistantAPIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="conversation_unavailable",
            message="Conversation history is temporarily unavailable.",
            retryable=True,
        ) from exc

    try:
        result = await request.app.state.llm_service.reply(
            payload.message,
            history=history,
            system_prompt=SYSTEM_PROMPT,
        )
    except LLMProviderError as exc:
        raise AssistantAPIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="assistant_unavailable",
            message="The language model is temporarily unavailable.",
            retryable=True,
        ) from exc

    updated_history = [
        *history,
        LLMMessage(role="user", content=payload.message),
        LLMMessage(role="assistant", content=result.text),
    ][-settings.conversation_max_messages :]
    try:
        await store.save(conversation_id, updated_history)
    except Exception as exc:
        raise AssistantAPIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="conversation_unavailable",
            message="Conversation history could not be saved.",
            retryable=True,
        ) from exc

    return ChatResponse(
        conversation_id=conversation_id,
        message=result.text,
        suggested_prompts=[
            "Show me products by category",
            "Help me compare two products",
        ],
    )

