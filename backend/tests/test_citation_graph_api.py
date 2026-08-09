from hashlib import sha256

import pytest
from app.domain.source import (
    BibliographicIdentifierKind,
    IdentifierObservationRole,
    SourceBundle,
    SourceDocument,
    SourceIdentifier,
    SourceReference,
    SourceType,
)
from app.main import app
from app.repositories.source_repository import get_source_repository
from app.repositories.workspace_repository import get_workspace_repository
from fastapi.testclient import TestClient

client = TestClient(app)
DOI = "10.1000/verity.test"
DOI_URL = f"https://doi.org/{DOI}"


@pytest.fixture(autouse=True)
def clear_citation_graph_state() -> None:
    get_workspace_repository().clear()
    get_source_repository().clear()
    yield
    get_workspace_repository().clear()
    get_source_repository().clear()


def _document(source_id: str, title: str, url: str | None = None) -> SourceDocument:
    material = f"{source_id}|{title}|{url or ''}".encode()
    return SourceDocument(
        source_id=source_id,
        source_type=SourceType.PUBLIC_URL if url else SourceType.DOCUMENT,
        title=title,
        filename=None if url else f"{source_id}.txt",
        url=url,
        source_format="html" if url else "txt",
        mime_type="text/html" if url else "text/plain",
        content_hash=sha256(material).hexdigest(),
        size_bytes=len(material),
        metadata={"requested_url": url, "final_url": url} if url else {},
    )


def _seed_citing_source() -> SourceDocument:
    source_id = "src_citing"
    document = _document(source_id, "Citing memo")
    reference = SourceReference(
        reference_id="ref_doi_target",
        source_id=source_id,
        target_url=DOI_URL,
        normalized_target_url=DOI_URL,
        reference_text=f"Primary work DOI:{DOI}",
        extraction_method="fixture",
    )
    identifier = SourceIdentifier(
        identifier_id="bid_reference_doi",
        source_id=source_id,
        kind=BibliographicIdentifierKind.DOI,
        raw_value=DOI,
        normalized_value=DOI,
        role=IdentifierObservationRole.REFERENCE,
        reference_id=reference.reference_id,
        context_text=reference.reference_text,
        extraction_method="reference_text_identifier_v1",
    )
    get_source_repository().save(
        SourceBundle(
            document=document,
            spans=[],
            references=[reference],
            identifiers=[identifier],
        )
    )
    return document


def _seed_attested_target(source_id: str, title: str) -> SourceDocument:
    document = _document(source_id, title, DOI_URL)
    identifier = SourceIdentifier(
        identifier_id=f"bid_{source_id}",
        source_id=source_id,
        kind=BibliographicIdentifierKind.DOI,
        raw_value=DOI,
        normalized_value=DOI,
        role=IdentifierObservationRole.SOURCE_IDENTITY,
        context_text=DOI_URL,
        extraction_method="source_url_identifier_v1",
    )
    get_source_repository().save(
        SourceBundle(document=document, spans=[], identifiers=[identifier])
    )
    return document


def _workspace_with(*documents: SourceDocument) -> str:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Citation graph"},
    ).json()
    workspace_id = workspace["workspace_id"]
    for document in documents:
        assert client.put(
            f"/api/v1/workspaces/{workspace_id}/sources/{document.source_id}"
        ).status_code == 200
    return workspace_id


def test_url_and_identifier_evidence_merge_into_one_directed_edge() -> None:
    citing = _seed_citing_source()
    target = _seed_attested_target("src_target", "Attested DOI work")
    workspace_id = _workspace_with(citing, target)

    response = client.get(f"/api/v1/workspaces/{workspace_id}/citation-graph")
    assert response.status_code == 200
    graph = response.json()

    assert graph["graph_version"] == "explicit-citation-graph-v1"
    assert graph["summary"] == {
        "source_count": 2,
        "edge_count": 1,
        "sources_with_outgoing_count": 1,
        "sources_with_incoming_count": 1,
        "url_reference_evidence_count": 1,
        "identifier_reference_evidence_count": 1,
        "unresolved_url_reference_count": 0,
        "ambiguous_url_reference_count": 0,
        "unresolved_identifier_reference_count": 0,
        "ambiguous_identifier_reference_count": 0,
        "self_edge_count": 0,
    }
    edge = graph["edges"][0]
    assert edge["source_id"] == citing.source_id
    assert edge["target_source_id"] == target.source_id
    assert edge["mechanisms"] == ["bibliographic_identifier", "url_reference"]
    assert edge["url_reference_ids"] == ["ref_doi_target"]
    assert edge["identifier_ids"] == ["bid_reference_doi"]
    assert edge["bibliographic_identities"] == [f"doi:{DOI}"]
    assert edge["evidence_count"] == 2
    assert "Shared identifier mentions never create citation edges" in graph["interpretation_note"]


def test_ambiguous_targets_are_counted_but_excluded_from_topology() -> None:
    citing = _seed_citing_source()
    first = _seed_attested_target("src_target_one", "Target one")
    second = _seed_attested_target("src_target_two", "Target two")
    workspace_id = _workspace_with(citing, first, second)

    graph = client.get(f"/api/v1/workspaces/{workspace_id}/citation-graph").json()

    assert graph["summary"]["edge_count"] == 0
    assert graph["summary"]["ambiguous_url_reference_count"] == 1
    assert graph["summary"]["ambiguous_identifier_reference_count"] == 1
    assert graph["summary"]["url_reference_evidence_count"] == 0
    assert graph["summary"]["identifier_reference_evidence_count"] == 0
    assert graph["edges"] == []


def test_shared_mentions_do_not_create_citation_edges() -> None:
    left = client.post(
        "/api/v1/documents/upload",
        files={"file": ("left.txt", f"Mention DOI:{DOI}".encode(), "text/plain")},
    ).json()
    right = client.post(
        "/api/v1/documents/upload",
        files={"file": ("right.txt", f"Mention DOI:{DOI}".encode(), "text/plain")},
    ).json()
    documents = []
    for bundle in (left, right):
        stored = get_source_repository().get(bundle["document"]["source_id"])
        assert stored is not None
        documents.append(stored.document)
    workspace_id = _workspace_with(*documents)

    graph = client.get(f"/api/v1/workspaces/{workspace_id}/citation-graph").json()
    assert graph["summary"]["edge_count"] == 0
    assert graph["summary"]["identifier_reference_evidence_count"] == 0
    assert graph["summary"]["unresolved_identifier_reference_count"] == 0


def test_missing_workspace_citation_graph_returns_404() -> None:
    response = client.get("/api/v1/workspaces/ws_missing/citation-graph")
    assert response.status_code == 404
