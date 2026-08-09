from hashlib import sha256

import pytest
from app.domain.source import SourceBundle, SourceDocument, SourceType
from app.main import app
from app.repositories.source_repository import get_source_repository
from app.repositories.workspace_repository import get_workspace_repository
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_lineage_state() -> None:
    get_workspace_repository().clear()
    get_source_repository().clear()
    yield
    get_workspace_repository().clear()
    get_source_repository().clear()


def test_workspace_reference_lineage_resolves_uploaded_explicit_url() -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Citation lineage"},
    ).json()
    workspace_id = workspace["workspace_id"]

    target = SourceDocument(
        source_id="src_target_web",
        source_type=SourceType.PUBLIC_URL,
        title="Target report",
        url="https://example.com/research/nvidia-networking",
        source_format="html",
        mime_type="text/html",
        content_hash=sha256(b"target").hexdigest(),
        size_bytes=6,
        metadata={
            "requested_url": "https://example.com/research/nvidia-networking#top",
            "final_url": "https://example.com/research/nvidia-networking",
        },
    )
    get_source_repository().save(SourceBundle(document=target, spans=[]))

    upload = client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "research-note.txt",
                b"Primary source: https://example.com/research/nvidia-networking#methods",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 201
    citing_bundle = upload.json()
    citing_source_id = citing_bundle["document"]["source_id"]
    assert len(citing_bundle["references"]) == 1
    reference = citing_bundle["references"][0]
    assert reference["span_id"] == citing_bundle["spans"][0]["span_id"]
    assert reference["page_number"] == 1
    assert reference["paragraph_number"] == 1

    assert client.put(
        f"/api/v1/workspaces/{workspace_id}/sources/{citing_source_id}"
    ).status_code == 200
    assert client.put(
        f"/api/v1/workspaces/{workspace_id}/sources/{target.source_id}"
    ).status_code == 200

    response = client.get(f"/api/v1/workspaces/{workspace_id}/reference-lineage")
    assert response.status_code == 200
    lineage = response.json()
    assert lineage["lineage_version"] == "explicit-reference-lineage-v3-wikipedia-citations"
    assert lineage["summary"] == {
        "source_count": 2,
        "reference_count": 1,
        "resolved_workspace_reference_count": 1,
        "ambiguous_workspace_reference_count": 0,
        "external_reference_count": 0,
        "self_reference_count": 0,
    }
    edge = lineage["references"][0]
    assert edge["source_id"] == citing_source_id
    assert edge["resolution"] == "workspace_unique"
    assert edge["target_source_ids"] == [target.source_id]
    assert edge["normalized_target_url"] == target.url
    assert edge["page_number"] == 1
    assert edge["paragraph_number"] == 1
    assert "does not prove quotation" in lineage["interpretation_note"]


def test_missing_workspace_reference_lineage_returns_404() -> None:
    response = client.get("/api/v1/workspaces/ws_missing/reference-lineage")
    assert response.status_code == 404
