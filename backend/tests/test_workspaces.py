import pytest
from app.main import app
from app.repositories.source_repository import get_source_repository
from app.repositories.workspace_repository import get_workspace_repository
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_persistent_state() -> None:
    workspaces = get_workspace_repository()
    sources = get_source_repository()
    workspaces.clear()
    sources.clear()
    yield
    workspaces.clear()
    sources.clear()


def test_workspace_combines_persisted_source_and_is_idempotent() -> None:
    created = client.post(
        "/api/v1/workspaces",
        json={
            "name": "  NVIDIA   Research  ",
            "description": "Documents and public evidence",
        },
    )
    assert created.status_code == 201
    workspace = created.json()
    assert workspace["name"] == "NVIDIA Research"
    assert workspace["source_count"] == 0

    uploaded = client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "workspace-evidence.txt",
                b"NVIDIA acquired Mellanox Technologies.",
                "text/plain",
            )
        },
    )
    assert uploaded.status_code == 201
    source_id = uploaded.json()["document"]["source_id"]

    first_add = client.put(
        f"/api/v1/workspaces/{workspace['workspace_id']}/sources/{source_id}"
    )
    assert first_add.status_code == 200
    assert first_add.json()["source_count"] == 1
    assert first_add.json()["sources"][0]["source_id"] == source_id

    second_add = client.put(
        f"/api/v1/workspaces/{workspace['workspace_id']}/sources/{source_id}"
    )
    assert second_add.status_code == 200
    assert second_add.json()["source_count"] == 1

    listed = client.get("/api/v1/workspaces")
    assert listed.status_code == 200
    assert listed.json()[0]["source_count"] == 1

    generic_sources = client.get("/api/v1/sources")
    assert generic_sources.status_code == 200
    assert generic_sources.json()[0]["source_id"] == source_id

    fetched = client.get(f"/api/v1/sources/{source_id}")
    assert fetched.status_code == 200
    assert fetched.json() == uploaded.json()


def test_workspace_source_can_be_removed_without_deleting_source() -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Removable membership"},
    ).json()
    source = client.post(
        "/api/v1/documents/upload",
        files={"file": ("evidence.txt", b"Persistent source.", "text/plain")},
    ).json()["document"]

    client.put(
        f"/api/v1/workspaces/{workspace['workspace_id']}/sources/{source['source_id']}"
    )
    removed = client.delete(
        f"/api/v1/workspaces/{workspace['workspace_id']}/sources/{source['source_id']}"
    )

    assert removed.status_code == 200
    assert removed.json()["source_count"] == 0
    assert client.get(f"/api/v1/sources/{source['source_id']}").status_code == 200


def test_workspace_can_be_deleted_without_deleting_sources() -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Temporary workspace"},
    ).json()
    source = client.post(
        "/api/v1/documents/upload",
        files={"file": ("evidence.txt", b"Independent source.", "text/plain")},
    ).json()["document"]
    client.put(
        f"/api/v1/workspaces/{workspace['workspace_id']}/sources/{source['source_id']}"
    )

    deleted = client.delete(f"/api/v1/workspaces/{workspace['workspace_id']}")

    assert deleted.status_code == 204
    assert client.get(f"/api/v1/workspaces/{workspace['workspace_id']}").status_code == 404
    assert client.get(f"/api/v1/sources/{source['source_id']}").status_code == 200


def test_workspace_reports_missing_source_and_workspace() -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Error contracts"},
    ).json()

    missing_source = client.put(
        f"/api/v1/workspaces/{workspace['workspace_id']}/sources/src_missing"
    )
    missing_workspace = client.get("/api/v1/workspaces/ws_missing")

    assert missing_source.status_code == 404
    assert missing_source.json()["detail"] == "Source not found."
    assert missing_workspace.status_code == 404
