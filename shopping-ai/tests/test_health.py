from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


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

