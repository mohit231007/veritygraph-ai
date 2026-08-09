from hashlib import sha256

import pytest
from app.domain.source import SourceBundle, SourceDocument, SourceSpan, SourceType
from app.main import app
from app.repositories.source_repository import get_source_repository
from app.repositories.workspace_repository import get_workspace_repository
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_retrieval_evaluation_state() -> None:
    get_workspace_repository().clear()
    get_source_repository().clear()
    yield
    get_workspace_repository().clear()
    get_source_repository().clear()


def _seed_source(source_id: str, filename: str, span_id: str) -> SourceDocument:
    text = "Evidence topic"
    span = SourceSpan(
        span_id=span_id,
        source_id=source_id,
        text=text,
        paragraph_number=1,
        char_start=0,
        char_end=len(text),
    )
    document = SourceDocument(
        source_id=source_id,
        source_type=SourceType.DOCUMENT,
        title=filename.removesuffix(".txt"),
        filename=filename,
        source_format="txt",
        mime_type="text/plain",
        content_hash=sha256(f"{source_id}|{text}".encode()).hexdigest(),
        size_bytes=len(text.encode()),
    )
    get_source_repository().save(SourceBundle(document=document, spans=[span]))
    return document


def _workspace_with(*documents: SourceDocument) -> str:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Retrieval evaluation"},
    ).json()
    workspace_id = workspace["workspace_id"]
    for document in documents:
        assert client.put(
            f"/api/v1/workspaces/{workspace_id}/sources/{document.source_id}"
        ).status_code == 200
    return workspace_id


def test_retrieval_evaluation_reports_exact_recall_precision_and_mrr() -> None:
    first = _seed_source("src_a", "A.txt", "span_a")
    second = _seed_source("src_b", "B.txt", "span_b")
    workspace_id = _workspace_with(first, second)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/retrieval/evaluate",
        json={
            "cases": [
                {
                    "case_id": "first-ranked",
                    "query": "evidence topic",
                    "relevant_span_ids": ["span_a"],
                },
                {
                    "case_id": "second-ranked",
                    "query": "evidence topic",
                    "relevant_span_ids": ["span_b"],
                },
            ],
            "k_values": [1, 2],
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["evaluation_version"] == "retrieval-evaluation-v1"
    assert payload["retrieval_version"] == "provenance-bm25-retrieval-v1"
    assert payload["summary"] == {
        "workspace_source_count": 2,
        "indexed_span_count": 2,
        "case_count": 2,
        "unique_relevant_span_count": 2,
        "mean_reciprocal_rank": 0.75,
        "metrics_at_k": [
            {"k": 1, "mean_recall": 0.5, "mean_precision": 0.5, "hit_rate": 0.5},
            {"k": 2, "mean_recall": 1.0, "mean_precision": 0.5, "hit_rate": 1.0},
        ],
    }
    first_case, second_case = payload["cases"]
    assert first_case["retrieved_span_ids"] == ["span_a", "span_b"]
    assert first_case["first_relevant_rank"] == 1
    assert first_case["reciprocal_rank"] == 1.0
    assert second_case["retrieved_span_ids"] == ["span_a", "span_b"]
    assert second_case["first_relevant_rank"] == 2
    assert second_case["reciprocal_rank"] == 0.5
    assert "Citation context is not part" in payload["interpretation_note"]


def test_stale_relevant_span_label_fails_closed() -> None:
    source = _seed_source("src_a", "A.txt", "span_a")
    workspace_id = _workspace_with(source)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/retrieval/evaluate",
        json={
            "cases": [
                {
                    "case_id": "stale",
                    "query": "evidence",
                    "relevant_span_ids": ["span_missing"],
                }
            ]
        },
    )

    assert response.status_code == 422
    assert "unknown relevant span id(s): span_missing" in response.json()["detail"]


def test_duplicate_case_ids_fail_closed() -> None:
    source = _seed_source("src_a", "A.txt", "span_a")
    workspace_id = _workspace_with(source)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/retrieval/evaluate",
        json={
            "cases": [
                {
                    "case_id": "duplicate",
                    "query": "evidence",
                    "relevant_span_ids": ["span_a"],
                },
                {
                    "case_id": "duplicate",
                    "query": "topic",
                    "relevant_span_ids": ["span_a"],
                },
            ]
        },
    )

    assert response.status_code == 422
    assert "duplicate case_id 'duplicate'" in response.json()["detail"]


def test_missing_workspace_retrieval_evaluation_returns_404() -> None:
    response = client.post(
        "/api/v1/workspaces/ws_missing/retrieval/evaluate",
        json={
            "cases": [
                {
                    "case_id": "missing",
                    "query": "evidence",
                    "relevant_span_ids": ["span_a"],
                }
            ]
        },
    )
    assert response.status_code == 404
