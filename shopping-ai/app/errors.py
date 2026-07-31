import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.models import ErrorResponse

logger = logging.getLogger("shopping_ai.errors")


class AssistantAPIError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        error_code: str,
        message: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.retryable = retryable


def _response(
    request: Request,
    *,
    status_code: int,
    error_code: str,
    message: str,
    retryable: bool,
) -> JSONResponse:
    payload = ErrorResponse(
        error_code=error_code,
        message=message,
        retryable=retryable,
        correlation_id=getattr(request.state, "request_id", "unavailable"),
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(by_alias=True, mode="json"),
    )


async def assistant_error_handler(request: Request, exc: AssistantAPIError) -> JSONResponse:
    return _response(
        request,
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        retryable=exc.retryable,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.info(
        "request_validation_failed",
        extra={"request_id": getattr(request.state, "request_id", "unavailable")},
    )
    return _response(
        request,
        status_code=422,
        error_code="invalid_request",
        message="The request does not match the assistant contract.",
        retryable=False,
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unexpected_error",
        exc_info=exc,
        extra={"request_id": getattr(request.state, "request_id", "unavailable")},
    )
    return _response(
        request,
        status_code=500,
        error_code="internal_error",
        message="The shopping assistant could not process the request.",
        retryable=True,
    )

