import pytest
from app.ingestion.web import FixtureWebFetcher
from app.main import app
from app.repositories.source_repository import get_source_repository
from app.services.web_ingestion import get_web_fetcher
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def fixture_web_fetcher() -> None:
    repository = get_source_repository()
    repository.clear()
    app.dependency_overrides[get_web_fetcher] = FixtureWebFetcher
    yield
    app.dependency_overrides.pop(get_web_fetcher, None)
    repository.clear()


def test_public_url_import_becomes_canonical_evidence() -> None:
    response = client.post(
        "/api/v1/web/import",
        json={"url": "https://example.com/research/nvidia-networking"},
    )

    assert response.status_code == 201
    body = response.json()
    document = body["document"]
    spans = body["spans"]

    assert document["source_type"] == "public_url"
    assert document["title"] == "NVIDIA Networking Research"
    assert document["url"] == "https://example.com/research/nvidia-networking"
    assert document["source_format"] == "html"
    assert document["metadata"]["redirect_count"] == 0
    assert document["metadata"]["hostname"] == "example.com"
    assert document["metadata"]["span_count"] == len(spans)
    assert len(document["content_hash"]) == 64
    assert spans
    assert all(span["section"] == "Main content" for span in spans)
    assert all(span["page_number"] is None for span in spans)
    assert any("Mellanox Technologies" in span["text"] for span in spans)
    assert not any("Footer noise" in span["text"] for span in spans)

    stored = client.get(f"/api/v1/documents/{document['source_id']}")
    assert stored.status_code == 200
    assert stored.json() == body


def test_public_url_request_rejects_too_short_value() -> None:
    response = client.post("/api/v1/web/import", json={"url": "http://"})

    assert response.status_code == 422
