from hashlib import sha256

import pytest
from app.domain.source import SourceBundle, SourceDocument, SourceReference, SourceSpan, SourceType
from app.main import app
from app.repositories.source_repository import get_source_repository
from app.repositories.workspace_repository import get_workspace_repository
from fastapi.testclient import TestClient

client = TestClient(app)
TARGET_URL = "https://example.com/research/evidence-pack-target"


@pytest.fixture(autouse=True)
def clear_evidence_pack_state() -> None:
    get_workspace_repository().clear()
    get_source_repository().clear()
    yield
    get_workspace_repository().clear()
    get_source_repository().clear()


def _save_source(
    source_id: str,
    title: str,
    span_texts: list[str],
    *,
    url: str | None = None,
    references: list[SourceReference] | None = None,
) -> SourceDocument:
    spans: list[SourceSpan] = []
    cursor = 0
    for index, text in enumerate(span_texts, start=1):
        spans.append(
            SourceSpan(
                span_id=f"span_{source_id}_{index}",
                source_id=source_id,
                text=text,
                section="Main content",
                paragraph_number=index,
                char_start=cursor,
                char_end=cursor + len(text),
            )
        )
        cursor += len(text) + 2

    joined = "\n\n".join(span_texts)
    document = SourceDocument(
        source_id=source_id,
        source_type=SourceType.PUBLIC_URL if url else SourceType.DOCUMENT,
        title=title,
        filename=None if url else f"{title}.txt",
        url=url,
        source_format="html" if url else "txt",
        mime_type="text/html" if url else "text/plain",
        content_hash=sha256(joined.encode()).hexdigest(),
        size_bytes=len(joined.encode()),
        metadata={"requested_url": url, "final_url": url} if url else {},
    )
    get_source_repository().save(
        SourceBundle(
            document=document,
            spans=spans,
            references=references or [],
        )
    )
    return document


def _workspace_with(*documents: SourceDocument) -> str:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Evidence pack workspace"},
    ).json()
    workspace_id = workspace["workspace_id"]
    for document in documents:
        assert client.put(
            f"/api/v1/workspaces/{workspace_id}/sources/{document.source_id}"
        ).status_code == 200
    return workspace_id


def test_evidence_pack_contains_direct_hits_but_not_neighbor_text() -> None:
    reference = SourceReference(
        reference_id="ref_pack_target",
        source_id="src_direct",
        target_url=TARGET_URL,
        normalized_target_url=TARGET_URL,
        context_text="Accelerated networking supports AI clusters.",
        extraction_method="fixture",
    )
    direct = _save_source(
        "src_direct",
        "Direct evidence",
        ["Accelerated networking supports AI clusters."],
        references=[reference],
    )
    neighbor = _save_source(
        "src_neighbor",
        "Citation neighbor",
        ["Marine ecology field observations from coastal wetlands."],
        url=TARGET_URL,
    )
    workspace_id = _workspace_with(direct, neighbor)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/retrieval/evidence-pack",
        json={"query": "accelerated networking"},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["pack_version"] == "grounded-evidence-pack-v1"
    assert payload["summary"]["selected_excerpt_count"] == 1
    assert payload["summary"]["citation_context_count"] == 1
    assert [item["source_id"] for item in payload["excerpts"]] == [direct.source_id]
    assert neighbor.source_id not in {item["source_id"] for item in payload["excerpts"]}
    assert "Marine ecology" not in " ".join(item["text"] for item in payload["excerpts"])
    assert payload["citation_context"][0]["neighbor_source_id"] == neighbor.source_id
    assert "metadata-only discovery context" in payload["interpretation_note"]


def test_evidence_pack_truncation_retains_exact_absolute_offsets() -> None:
    text = ("prefix " * 70) + "accelerated networking evidence" + (" suffix" * 70)
    source = _save_source("src_long", "Long source", [text])
    workspace_id = _workspace_with(source)

    payload = client.post(
        f"/api/v1/workspaces/{workspace_id}/retrieval/evidence-pack",
        json={
            "query": "accelerated networking",
            "max_chars_per_excerpt": 120,
            "max_total_chars": 500,
        },
    ).json()

    excerpt = payload["excerpts"][0]
    assert excerpt["truncated_before"] is True
    assert excerpt["truncated_after"] is True
    assert len(excerpt["text"]) == 120
    assert excerpt["excerpt_char_start"] > excerpt["span_char_start"]
    relative_start = excerpt["excerpt_char_start"] - excerpt["span_char_start"]
    relative_end = excerpt["excerpt_char_end"] - excerpt["span_char_start"]
    assert text[relative_start:relative_end] == excerpt["text"]
    assert "accelerated networking" in excerpt["text"]


def test_evidence_pack_source_cap_preserves_cross_source_diversity() -> None:
    first = _save_source(
        "src_first",
        "First",
        [
            "Accelerated networking evidence alpha alpha alpha.",
            "Accelerated networking evidence beta beta beta.",
        ],
    )
    second = _save_source(
        "src_second",
        "Second",
        ["Accelerated networking evidence from an independent workspace source."],
    )
    workspace_id = _workspace_with(first, second)

    payload = client.post(
        f"/api/v1/workspaces/{workspace_id}/retrieval/evidence-pack",
        json={
            "query": "accelerated networking evidence",
            "max_excerpts": 3,
            "max_excerpts_per_source": 1,
        },
    ).json()

    selected_sources = [item["source_id"] for item in payload["excerpts"]]
    assert selected_sources.count(first.source_id) == 1
    assert selected_sources.count(second.source_id) == 1
    assert payload["summary"]["selected_source_count"] == 2
    assert payload["summary"]["skipped_by_source_cap"] >= 1


def test_missing_workspace_evidence_pack_returns_404() -> None:
    response = client.post(
        "/api/v1/workspaces/ws_missing/retrieval/evidence-pack",
        json={"query": "evidence"},
    )
    assert response.status_code == 404
