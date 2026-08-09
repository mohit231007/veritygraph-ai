import pytest
from app.main import app
from app.repositories.source_repository import get_source_repository
from app.repositories.workspace_repository import get_workspace_repository
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_wikipedia_citation_api_state() -> None:
    get_workspace_repository().clear()
    get_source_repository().clear()
    yield
    get_workspace_repository().clear()
    get_source_repository().clear()


def test_wikipedia_import_and_workspace_lineage_expose_selected_citation_bridge() -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Wikipedia citation API"},
    ).json()

    imported = client.post(
        "/api/v1/wikipedia/import",
        json={"page_id": 609498, "section_indices": ["1"]},
    )
    assert imported.status_code == 201
    bundle = imported.json()
    assert [span["text"] for span in bundle["spans"]] == [
        "Nvidia was founded in 1993.",
        (
            "The company expanded from graphics into accelerated computing "
            "and data-center systems."
        ),
    ]
    assert len(bundle["references"]) == 1

    reference = bundle["references"][0]
    assert reference["normalized_target_url"] == (
        "https://example.com/research/nvidia-founding"
    )
    assert reference["span_id"] == bundle["spans"][0]["span_id"]
    assert reference["context_text"] == "Nvidia was founded in 1993."
    assert reference["reference_text"] == (
        "Example Research. Nvidia founding timeline. Retrieved 2026."
    )
    assert reference["citation_label"] == "[1]"
    assert reference["citation_marker"] == "cite_note-fixture-history-1"
    assert reference["extraction_method"] == "mediawiki_inline_citation_v1"
    assert "example.com" not in bundle["spans"][0]["text"]

    added = client.put(
        f"/api/v1/workspaces/{workspace['workspace_id']}/sources/"
        f"{bundle['document']['source_id']}"
    )
    assert added.status_code == 200

    lineage_response = client.get(
        f"/api/v1/workspaces/{workspace['workspace_id']}/reference-lineage"
    )
    assert lineage_response.status_code == 200
    lineage = lineage_response.json()
    assert lineage["lineage_version"] == (
        "explicit-reference-lineage-v3-wikipedia-citations"
    )
    assert lineage["summary"]["reference_count"] == 1
    assert lineage["summary"]["external_reference_count"] == 1
    edge = lineage["references"][0]
    assert edge["source_id"] == bundle["document"]["source_id"]
    assert edge["resolution"] == "external"
    assert edge["span_id"] == bundle["spans"][0]["span_id"]
    assert edge["citation_label"] == "[1]"
    assert edge["citation_marker"] == "cite_note-fixture-history-1"
    assert edge["reference_text"] == (
        "Example Research. Nvidia founding timeline. Retrieved 2026."
    )
