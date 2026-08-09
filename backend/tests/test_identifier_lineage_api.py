import pytest
from app.main import app
from app.repositories.source_repository import get_source_repository
from app.repositories.workspace_repository import get_workspace_repository
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_identifier_lineage_state() -> None:
    get_workspace_repository().clear()
    get_source_repository().clear()
    yield
    get_workspace_repository().clear()
    get_source_repository().clear()


def _upload(name: str, text: str) -> dict:
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": (name, text.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 201
    return response.json()


def test_identifier_lineage_matches_same_doi_across_distinct_sources() -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Bibliographic identity"},
    ).json()
    workspace_id = workspace["workspace_id"]

    left = _upload("left.txt", "Primary record DOI:10.1000/VERITY.TEST")
    right = _upload("right.txt", "Secondary record doi:10.1000/verity.test")
    for bundle in (left, right):
        assert bundle["document"]["metadata"]["identifier_count"] == 1
        assert len(bundle["identifiers"]) == 1
        source_id = bundle["document"]["source_id"]
        assert client.put(
            f"/api/v1/workspaces/{workspace_id}/sources/{source_id}"
        ).status_code == 200

    response = client.get(f"/api/v1/workspaces/{workspace_id}/identifier-lineage")
    assert response.status_code == 200
    lineage = response.json()
    assert lineage["lineage_version"] == "bibliographic-identity-lineage-v1"
    assert lineage["summary"] == {
        "source_count": 2,
        "observation_count": 2,
        "unique_identifier_count": 1,
        "matched_observation_count": 2,
        "ambiguous_observation_count": 0,
        "reference_linked_observation_count": 0,
    }
    assert {item["normalized_value"] for item in lineage["identifiers"]} == {
        "10.1000/verity.test"
    }
    assert all(item["resolution"] == "workspace_unique" for item in lineage["identifiers"])
    for item in lineage["identifiers"]:
        assert item["source_id"] not in item["matching_source_ids"]
        assert len(item["matching_source_ids"]) == 1
    assert "does not prove citation" in lineage["interpretation_note"]


def test_identifier_lineage_keeps_duplicate_workspace_identity_ambiguous() -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Ambiguous identity"},
    ).json()
    workspace_id = workspace["workspace_id"]

    for index in range(3):
        bundle = _upload(
            f"source-{index}.txt",
            f"Record {index} DOI:10.1000/VERITY.TEST",
        )
        source_id = bundle["document"]["source_id"]
        assert client.put(
            f"/api/v1/workspaces/{workspace_id}/sources/{source_id}"
        ).status_code == 200

    lineage = client.get(
        f"/api/v1/workspaces/{workspace_id}/identifier-lineage"
    ).json()
    assert lineage["summary"]["observation_count"] == 3
    assert lineage["summary"]["matched_observation_count"] == 3
    assert lineage["summary"]["ambiguous_observation_count"] == 3
    assert all(
        item["resolution"] == "workspace_ambiguous"
        and len(item["matching_source_ids"]) == 2
        for item in lineage["identifiers"]
    )


def test_missing_workspace_identifier_lineage_returns_404() -> None:
    response = client.get("/api/v1/workspaces/ws_missing/identifier-lineage")
    assert response.status_code == 404
