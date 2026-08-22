from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.catalog import CatalogClient
from app.services.retrieval import HybridProductSearch


def test_health_endpoint() -> None:
    application = create_app(Settings(app_env="test", _env_file=None))

    with TestClient(application) as client:
        response = client.get("/health", headers={"x-request-id": "test-request"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "skinet-shopping-ai",
        "version": "0.1.0",
    }
    assert response.headers["x-request-id"] == "test-request"


def test_semantic_search_is_lazy_and_does_not_block_health() -> None:
    catalog_client = AsyncMock(spec=CatalogClient)
    application = create_app(
        Settings(app_env="test", semantic_search_enabled=True, _env_file=None),
        catalog_client=catalog_client,
    )

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert isinstance(application.state.product_search, HybridProductSearch)
    catalog_client.search_products.assert_not_awaited()

