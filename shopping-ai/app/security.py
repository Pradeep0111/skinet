from hmac import compare_digest

from fastapi import Header, Request, status

from app.errors import AssistantAPIError


async def require_internal_service_key(
    request: Request,
    x_assistant_service_key: str | None = Header(
        default=None,
        alias="X-Assistant-Service-Key",
    ),
) -> None:
    configured_secret = request.app.state.settings.internal_service_key
    if configured_secret is None:
        raise AssistantAPIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="assistant_not_configured",
            message="Internal assistant access is not configured.",
            retryable=False,
        )

    configured_value = configured_secret.get_secret_value()
    supplied_value = x_assistant_service_key or ""
    if not configured_value or not compare_digest(supplied_value, configured_value):
        raise AssistantAPIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="invalid_service_key",
            message="A valid internal service credential is required.",
            retryable=False,
        )

