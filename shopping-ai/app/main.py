from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app import __version__
from app.agents import ShoppingAgent
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.config import Settings, get_settings
from app.errors import (
    AssistantAPIError,
    assistant_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from app.observability import RequestLoggingMiddleware, configure_logging
from app.services.catalog import CatalogClient, create_catalog_client
from app.services.conversation import ConversationStore, create_conversation_store
from app.services.llm import LLMProvider, LLMService
from app.services.llm.factory import create_llm_provider
from app.tools import CatalogTools


def create_app(
    settings: Settings | None = None,
    *,
    llm_provider: LLMProvider | None = None,
    conversation_store: ConversationStore | None = None,
    catalog_client: CatalogClient | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    resolved_store = conversation_store or create_conversation_store(resolved_settings)
    resolved_catalog_client = catalog_client or create_catalog_client(resolved_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        yield
        await application.state.conversation_store.close()
        await application.state.catalog_client.close()

    application = FastAPI(
        title=resolved_settings.app_name,
        version=__version__,
        docs_url="/docs" if resolved_settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.conversation_store = resolved_store
    application.state.catalog_client = resolved_catalog_client
    application.state.catalog_tools = CatalogTools(resolved_catalog_client)
    application.state.shopping_agent = ShoppingAgent(application.state.catalog_tools)
    application.state.llm_service = LLMService(
        llm_provider or create_llm_provider(resolved_settings)
    )
    application.add_middleware(RequestLoggingMiddleware)
    application.add_exception_handler(AssistantAPIError, assistant_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(Exception, unexpected_error_handler)
    application.include_router(health_router)
    application.include_router(chat_router)
    return application


app = create_app()
