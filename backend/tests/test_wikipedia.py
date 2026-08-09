import pytest
from app.ingestion.wikipedia import FixtureWikipediaProvider
from app.main import app
from app.repositories.source_repository import get_source_repository
from app.services.wikipedia_ingestion import get_wikipedia_provider
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def fixture_wikipedia_provider() -> None:
    repository = get_source_repository()
    repository.clear()
    app.dependency_overrides[get_wikipedia_provider] = FixtureWikipediaProvider
    yield
    app.dependency_overrides.pop(get_wikipedia_provider, None)
    repository.clear()


def test_wikipedia_search_returns_public_page_candidates() -> None:
    response = client.get("/api/v1/wikipedia/search", params={"q": "NVIDIA", "limit": 5})

    assert response.status_code == 200
    results = response.json()
    assert results[0]["page_id"] == FixtureWikipediaProvider.PAGE_ID
    assert results[0]["title"] == "Nvidia"
    assert "technology company" in results[0]["snippet"]


def test_wikipedia_outline_exposes_selectable_sections() -> None:
    response = client.get(
        f"/api/v1/wikipedia/pages/{FixtureWikipediaProvider.PAGE_ID}/outline"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Nvidia"
    assert body["revision_id"] == 123456789
    assert [section["title"] for section in body["sections"]] == [
        "Overview",
        "History",
        "Products",
    ]


def test_selected_wikipedia_sections_become_canonical_evidence() -> None:
    response = client.post(
        "/api/v1/wikipedia/import",
        json={
            "page_id": FixtureWikipediaProvider.PAGE_ID,
            "section_indices": ["0", "1"],
        },
    )

    assert response.status_code == 201
    body = response.json()
    document = body["document"]
    spans = body["spans"]

    assert document["source_type"] == "wikipedia"
    assert document["title"] == "Nvidia"
    assert document["url"].startswith("https://en.wikipedia.org/")
    assert document["metadata"]["revision_id"] == 123456789
    assert document["metadata"]["selected_section_count"] == 2
    assert {span["section"] for span in spans} == {"Overview", "History"}
    assert spans[0]["paragraph_number"] == 1
    assert spans[0]["char_start"] == 0
    assert spans[0]["char_end"] > spans[0]["char_start"]

    stored = client.get(f"/api/v1/documents/{document['source_id']}")
    assert stored.status_code == 200
    assert stored.json() == body


def test_unknown_wikipedia_page_returns_404() -> None:
    response = client.get("/api/v1/wikipedia/pages/999/outline")

    assert response.status_code == 404


def test_unknown_wikipedia_section_is_rejected() -> None:
    response = client.post(
        "/api/v1/wikipedia/import",
        json={
            "page_id": FixtureWikipediaProvider.PAGE_ID,
            "section_indices": ["99"],
        },
    )

    assert response.status_code == 422
    assert "Unknown Wikipedia section" in response.json()["detail"]


def test_wikipedia_search_validates_query_length() -> None:
    response = client.get("/api/v1/wikipedia/search", params={"q": "x"})

    assert response.status_code == 422
