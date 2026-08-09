from hashlib import sha256

import pytest
from app.domain.source import (
    BibliographicIdentifierKind,
    IdentifierObservationRole,
    SourceBundle,
    SourceDocument,
    SourceIdentifier,
    SourceType,
)
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


def _seed_attested_doi_source(source_id: str, doi: str) -> SourceDocument:
    url = f"https://doi.org/{doi}"
    document = SourceDocument(
        source_id=source_id,
        source_type=SourceType.PUBLIC_URL,
        title="Attested DOI work",
        url=url,
        source_format="html",
        mime_type="text/html",
        content_hash=sha256(url.encode("utf-8")).hexdigest(),
        size_bytes=len(url.encode("utf-8")),
        metadata={"requested_url": url, "final_url": url},
    )
    identifier = SourceIdentifier(
        identifier_id=f"bid_{source_id}",
        source_id=source_id,
        kind=BibliographicIdentifierKind.DOI,
        raw_value=doi,
        normalized_value=doi.lower(),
        role=IdentifierObservationRole.SOURCE_IDENTITY,
        context_text=url,
        extraction_method="source_url_identifier_v1",
    )
    get_source_repository().save(
        SourceBundle(document=document, spans=[], identifiers=[identifier])
    )
    return document


def test_same_doi_mentions_are_shared_observations_not_source_identity() -> None:
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
    assert lineage["lineage_version"] == "bibliographic-identity-lineage-v2-source-attestation"
    assert lineage["summary"] == {
        "source_count": 2,
        "observation_count": 2,
        "unique_identifier_count": 1,
        "matched_observation_count": 2,
        "ambiguous_observation_count": 0,
        "reference_linked_observation_count": 0,
        "source_identity_observation_count": 0,
        "resolved_identity_target_observation_count": 0,
        "ambiguous_identity_target_observation_count": 0,
    }
    assert {item["normalized_value"] for item in lineage["identifiers"]} == {
        "10.1000/verity.test"
    }
    assert all(item["resolution"] == "workspace_unique" for item in lineage["identifiers"])
    assert all(
        item["identity_target_resolution"] == "no_workspace_match"
        and item["identity_target_source_ids"] == []
        for item in lineage["identifiers"]
    )
    assert "shared identifier observation only means" in lineage["interpretation_note"].lower()


def test_observation_resolves_only_to_attested_source_identity() -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Attested target"},
    ).json()
    workspace_id = workspace["workspace_id"]

    mention = _upload("mention.txt", "Discussed work DOI:10.1000/VERITY.TEST")
    mention_source_id = mention["document"]["source_id"]
    attested = _seed_attested_doi_source("src_attested_doi", "10.1000/verity.test")

    for source_id in (mention_source_id, attested.source_id):
        assert client.put(
            f"/api/v1/workspaces/{workspace_id}/sources/{source_id}"
        ).status_code == 200

    lineage = client.get(
        f"/api/v1/workspaces/{workspace_id}/identifier-lineage"
    ).json()
    assert lineage["summary"]["source_identity_observation_count"] == 1
    assert lineage["summary"]["resolved_identity_target_observation_count"] == 1

    mention_observation = next(
        item for item in lineage["identifiers"] if item["source_id"] == mention_source_id
    )
    assert mention_observation["role"] == "mention"
    assert mention_observation["identity_target_resolution"] == "workspace_unique"
    assert mention_observation["identity_target_source_ids"] == [attested.source_id]
    assert mention_observation["identity_target_labels"] == ["Attested DOI work"]

    identity_observation = next(
        item for item in lineage["identifiers"] if item["source_id"] == attested.source_id
    )
    assert identity_observation["role"] == "source_identity"
    assert identity_observation["identity_target_resolution"] == "no_workspace_match"


def test_duplicate_mentions_remain_ambiguous_without_identity_targets() -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Ambiguous observation"},
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
    assert lineage["summary"]["source_identity_observation_count"] == 0
    assert lineage["summary"]["resolved_identity_target_observation_count"] == 0
    assert all(
        item["resolution"] == "workspace_ambiguous"
        and len(item["matching_source_ids"]) == 2
        and item["identity_target_resolution"] == "no_workspace_match"
        for item in lineage["identifiers"]
    )


def test_missing_workspace_identifier_lineage_returns_404() -> None:
    response = client.get("/api/v1/workspaces/ws_missing/identifier-lineage")
    assert response.status_code == 404
