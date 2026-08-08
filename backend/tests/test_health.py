from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_contract() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "veritygraph-api",
        "version": "0.1.0",
    }


def test_openapi_is_available() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "VerityGraph AI API"
