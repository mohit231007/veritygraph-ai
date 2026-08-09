from pathlib import Path

import pytest
from app.core.config import get_settings
from app.main import app
from app.repositories.analysis_repository import (
    SqliteAnalysisRepository,
    get_analysis_repository,
)
from app.repositories.source_repository import get_source_repository
from app.repositories.workspace_repository import get_workspace_repository
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_analysis_state() -> None:
    analysis_repository = get_analysis_repository()
    workspace_repository = get_workspace_repository()
    source_repository = get_source_repository()
    analysis_repository.clear()
    workspace_repository.clear()
    source_repository.clear()
    yield
    analysis_repository.clear()
    workspace_repository.clear()
    source_repository.clear()


def create_workspace_with_evidence(text: str) -> tuple[str, str, str]:
    workspace_response = client.post(
        "/api/v1/workspaces",
        json={"name": "NLP evidence workspace"},
    )
    assert workspace_response.status_code == 201
    workspace_id = workspace_response.json()["workspace_id"]

    source_response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("evidence.txt", text.encode("utf-8"), "text/plain")},
    )
    assert source_response.status_code == 201
    bundle = source_response.json()
    source_id = bundle["document"]["source_id"]
    span_id = bundle["spans"][0]["span_id"]

    add_response = client.put(
        f"/api/v1/workspaces/{workspace_id}/sources/{source_id}"
    )
    assert add_response.status_code == 200
    return workspace_id, source_id, span_id


def entity_name_index(analysis: dict) -> dict[str, str]:
    return {
        entity["entity_id"]: entity["canonical_name"]
        for entity in analysis["entities"]
    }


def test_workspace_analysis_persists_entities_relations_and_exact_evidence() -> None:
    sentence = "Microsoft acquired GitHub in 2018."
    workspace_id, source_id, span_id = create_workspace_with_evidence(sentence)

    response = client.post(f"/api/v1/workspaces/{workspace_id}/analyses")

    assert response.status_code == 201
    analysis = response.json()
    run = analysis["run"]
    assert run["status"] == "completed"
    assert run["workspace_id"] == workspace_id
    assert run["model_name"] == "en_core_web_sm"
    assert run["model_version"]
    assert run["pipeline_version"] == "spacy-baseline-v1"
    assert run["extractor_version"] == "dependency-relations-v1"
    assert run["source_count"] == 1
    assert run["span_count"] == 1
    assert run["entity_count"] >= 2
    assert run["relation_count"] >= 1
    assert run["completed_at"] is not None
    assert run["duration_ms"] is not None

    names = entity_name_index(analysis)
    relation = next(
        relation
        for relation in analysis["relations"]
        if names[relation["subject_entity_id"]] == "Microsoft"
        and names[relation["object_entity_id"]] == "GitHub"
        and relation["predicate"] == "acquire"
    )
    assert relation["extraction_score"] == 0.92
    assert relation["extraction_method"] == "dependency_subject_object"
    assert relation["evidence"][0]["source_id"] == source_id
    assert relation["evidence"][0]["span_id"] == span_id
    assert relation["evidence"][0]["text"] == sentence

    latest = client.get(f"/api/v1/workspaces/{workspace_id}/analyses/latest")
    assert latest.status_code == 200
    assert latest.json() == analysis

    by_run = client.get(f"/api/v1/analyses/{run['run_id']}")
    assert by_run.status_code == 200
    assert by_run.json() == analysis

    fresh_repository = SqliteAnalysisRepository(Path(get_settings().database_path))
    restored = fresh_repository.get(run["run_id"])
    assert restored is not None
    assert restored.model_dump(mode="json") == analysis


def test_reanalysis_creates_new_immutable_run_and_latest_points_to_newest() -> None:
    workspace_id, _source_id, _span_id = create_workspace_with_evidence(
        "Microsoft acquired GitHub in 2018."
    )

    first = client.post(f"/api/v1/workspaces/{workspace_id}/analyses")
    second = client.post(f"/api/v1/workspaces/{workspace_id}/analyses")

    assert first.status_code == 201
    assert second.status_code == 201
    first_run = first.json()["run"]["run_id"]
    second_run = second.json()["run"]["run_id"]
    assert first_run != second_run

    runs = client.get(f"/api/v1/workspaces/{workspace_id}/analyses")
    assert runs.status_code == 200
    run_ids = {run["run_id"] for run in runs.json()}
    assert {first_run, second_run}.issubset(run_ids)

    latest = client.get(f"/api/v1/workspaces/{workspace_id}/analyses/latest")
    assert latest.status_code == 200
    assert latest.json()["run"]["run_id"] == second_run


def test_empty_workspace_cannot_be_analysed() -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Empty analysis workspace"},
    ).json()

    response = client.post(
        f"/api/v1/workspaces/{workspace['workspace_id']}/analyses"
    )

    assert response.status_code == 422
    assert "Add at least one source" in response.json()["detail"]


def test_missing_workspace_analysis_contracts_return_404() -> None:
    create_response = client.post("/api/v1/workspaces/ws_missing/analyses")
    latest_response = client.get("/api/v1/workspaces/ws_missing/analyses/latest")
    list_response = client.get("/api/v1/workspaces/ws_missing/analyses")
    run_response = client.get("/api/v1/analyses/run_missing")

    assert create_response.status_code == 404
    assert latest_response.status_code == 404
    assert list_response.status_code == 404
    assert run_response.status_code == 404
