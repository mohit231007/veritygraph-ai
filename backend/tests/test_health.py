from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_contract() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "veritygraph-api",
        "version": "0.4.0",
    }


def test_openapi_is_available() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "VerityGraph AI API"
    assert response.json()["info"]["version"] == "0.4.0"
