from hashlib import sha256

import pytest
from app.domain.source import SourceBundle, SourceDocument, SourceReference, SourceSpan, SourceType
from app.main import app
from app.repositories.source_repository import get_source_repository
from app.repositories.workspace_repository import get_workspace_repository
from fastapi.testclient import TestClient

client = TestClient(app)
TARGET_URL = "https://example.com/research/target"


@pytest.fixture(autouse=True)
def clear_retrieval_state() -> None:
    get_workspace_repository().clear()
    get_source_repository().clear()
    yield
    get_workspace_repository().clear()
    get_source_repository().clear()


def _document(
    source_id: str,
    title: str,
    text: str,
    *,
    url: str | None = None,
    references: list[SourceReference] | None = None,
) -> SourceDocument:
    span = SourceSpan(
        span_id=f"span_{source_id}",
        source_id=source_id,
        text=text,
        section="Main content",
        paragraph_number=1,
        char_start=0,
        char_end=len(text),
    )
    document = SourceDocument(
        source_id=source_id,
        source_type=SourceType.PUBLIC_URL if url else SourceType.DOCUMENT,
        title=title,
        filename=None if url else f"{title}.txt",
        url=url,
        source_format="html" if url else "txt",
        mime_type="text/html" if url else "text/plain",
        content_hash=sha256(text.encode()).hexdigest(),
        size_bytes=len(text.encode()),
        metadata={"requested_url": url, "final_url": url} if url else {},
    )
    get_source_repository().save(
        SourceBundle(
            document=document,
            spans=[span],
            references=references or [],
        )
    )
    return document


def _workspace_with(*documents: SourceDocument) -> str:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Retrieval workspace"},
    ).json()
    workspace_id = workspace["workspace_id"]
    for document in documents:
        assert client.put(
            f"/api/v1/workspaces/{workspace_id}/sources/{document.source_id}"
        ).status_code == 200
    return workspace_id


def test_lexical_hits_and_citation_neighbors_remain_separate() -> None:
    reference = SourceReference(
        reference_id="ref_target",
        source_id="src_direct",
        target_url=TARGET_URL,
        normalized_target_url=TARGET_URL,
        context_text="Accelerated networking supports AI clusters.",
        extraction_method="fixture",
    )
    direct = _document(
        "src_direct",
        "Direct evidence",
        "Accelerated networking supports AI clusters.",
        references=[reference],
    )
    neighbor = _document(
        "src_neighbor",
        "Connected target",
        "Marine ecology field observations from coastal wetlands.",
        url=TARGET_URL,
    )
    workspace_id = _workspace_with(direct, neighbor)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/retrieval/preview",
        json={"query": "accelerated networking", "limit": 8},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["retrieval_version"] == "provenance-bm25-retrieval-v1"
    assert payload["summary"] == {
        "workspace_source_count": 2,
        "indexed_span_count": 2,
        "query_term_count": 2,
        "direct_hit_count": 1,
        "direct_hit_source_count": 1,
        "citation_context_count": 1,
    }
    assert [hit["source_id"] for hit in payload["hits"]] == [direct.source_id]
    assert payload["hits"][0]["matched_terms"] == ["accelerated", "networking"]
    assert payload["hits"][0]["score"] > 0
    assert neighbor.source_id not in {hit["source_id"] for hit in payload["hits"]}

    context = payload["citation_context"][0]
    assert context["seed_source_id"] == direct.source_id
    assert context["direction"] == "outgoing"
    assert context["neighbor_source_id"] == neighbor.source_id
    assert context["mechanisms"] == ["url_reference"]
    assert "do not change hit scores" in payload["interpretation_note"]


def test_retrieval_ranking_is_deterministic_and_limit_is_applied() -> None:
    stronger = _document(
        "src_stronger",
        "Stronger",
        "Accelerated networking improves accelerated networking systems.",
    )
    weaker = _document(
        "src_weaker",
        "Weaker",
        "Networking systems are discussed here.",
    )
    workspace_id = _workspace_with(stronger, weaker)

    payload = client.post(
        f"/api/v1/workspaces/{workspace_id}/retrieval/preview",
        json={"query": "accelerated networking", "limit": 1},
    ).json()

    assert payload["summary"]["direct_hit_count"] == 1
    assert payload["hits"][0]["rank"] == 1
    assert payload["hits"][0]["source_id"] == stronger.source_id
    assert payload["hits"][0]["matched_terms"] == ["accelerated", "networking"]


def test_no_lexical_match_does_not_expand_graph_context() -> None:
    left = _document("src_left", "Left", "Accelerated networking evidence.")
    right = _document("src_right", "Right", "Unrelated biology evidence.")
    workspace_id = _workspace_with(left, right)

    payload = client.post(
        f"/api/v1/workspaces/{workspace_id}/retrieval/preview",
        json={"query": "quantum volcanology"},
    ).json()

    assert payload["summary"]["direct_hit_count"] == 0
    assert payload["summary"]["citation_context_count"] == 0
    assert payload["hits"] == []
    assert payload["citation_context"] == []


def test_missing_workspace_retrieval_returns_404() -> None:
    response = client.post(
        "/api/v1/workspaces/ws_missing/retrieval/preview",
        json={"query": "evidence"},
    )
    assert response.status_code == 404
