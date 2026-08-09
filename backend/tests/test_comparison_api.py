import pytest
from app.main import app
from app.repositories.analysis_repository import get_analysis_repository
from app.repositories.source_repository import get_source_repository
from app.repositories.workspace_repository import get_workspace_repository
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_comparison_state() -> None:
    get_analysis_repository().clear()
    get_workspace_repository().clear()
    get_source_repository().clear()
    yield
    get_analysis_repository().clear()
    get_workspace_repository().clear()
    get_source_repository().clear()


def upload_and_add(workspace_id: str, filename: str, text: str) -> str:
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, text.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 201
    source_id = response.json()["document"]["source_id"]
    added = client.put(f"/api/v1/workspaces/{workspace_id}/sources/{source_id}")
    assert added.status_code == 200
    return source_id


def test_comparison_api_uses_exact_run_sources_and_real_extracted_support() -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Corroboration workspace"},
    ).json()
    workspace_id = workspace["workspace_id"]

    first_source_id = upload_and_add(
        workspace_id,
        "source-one.txt",
        "Microsoft acquired GitHub. GitHub acquired OpenAI.",
    )
    second_source_id = upload_and_add(
        workspace_id,
        "source-two.txt",
        "Microsoft acquired GitHub. Amazon acquired Twitch.",
    )

    analysis_response = client.post(f"/api/v1/workspaces/{workspace_id}/analyses")
    assert analysis_response.status_code == 201
    analysis = analysis_response.json()
    run = analysis["run"]
    assert run["source_count"] == 2
    assert run["source_ids"] == [first_source_id, second_source_id]

    response = client.get(f"/api/v1/analyses/{run['run_id']}/comparison")
    latest = client.get(f"/api/v1/workspaces/{workspace_id}/comparison/latest")

    assert response.status_code == 200
    assert latest.status_code == 200
    assert response.json() == latest.json()
    comparison = response.json()
    assert comparison["comparison_version"] == "source-corroboration-v2-polarity"
    assert comparison["summary"]["source_count"] == 2
    assert comparison["summary"]["cross_source_claim_count"] >= 1
    assert comparison["summary"]["single_source_claim_count"] >= 2
    assert comparison["summary"]["contradiction_candidate_count"] == 0

    microsoft_github = next(
        claim
        for claim in comparison["claims"]
        if claim["subject_label"] == "Microsoft"
        and claim["predicate"] == "acquire"
        and claim["object_label"] == "GitHub"
    )
    assert microsoft_github["polarity"] == "affirmed"
    assert microsoft_github["support_level"] == "cross_source"
    assert microsoft_github["source_count"] == 2
    assert set(microsoft_github["source_ids"]) == {
        first_source_id,
        second_source_id,
    }

    profiles = {profile["label"]: profile for profile in comparison["sources"]}
    assert profiles["source-one.txt"]["claim_count"] >= 2
    assert profiles["source-two.txt"]["claim_count"] >= 2

    overlap = comparison["overlaps"][0]
    assert overlap["shared_claim_count"] >= 1
    assert 0.0 < overlap["jaccard_similarity"] <= 1.0
    assert "absence" in comparison["interpretation_note"].casefold()
    assert "contradiction" in comparison["interpretation_note"].casefold()


def test_comparison_api_detects_real_explicit_cross_source_negation() -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Contradiction workspace"},
    ).json()
    workspace_id = workspace["workspace_id"]

    affirmed_source_id = upload_and_add(
        workspace_id,
        "affirmed.txt",
        "Microsoft acquired GitHub.",
    )
    negated_source_id = upload_and_add(
        workspace_id,
        "negated.txt",
        "Microsoft did not acquire GitHub.",
    )

    analysis_response = client.post(f"/api/v1/workspaces/{workspace_id}/analyses")
    assert analysis_response.status_code == 201
    run_id = analysis_response.json()["run"]["run_id"]

    response = client.get(f"/api/v1/analyses/{run_id}/comparison")
    assert response.status_code == 200
    comparison = response.json()
    assert comparison["summary"]["contradiction_candidate_count"] == 1

    candidate = comparison["contradictions"][0]
    assert candidate["subject_label"] == "Microsoft"
    assert candidate["predicate"] == "acquire"
    assert candidate["object_label"] == "GitHub"
    assert candidate["affirmed_source_ids"] == [affirmed_source_id]
    assert candidate["negated_source_ids"] == [negated_source_id]
    assert {item["text"] for item in candidate["affirmed_evidence"]} == {
        "Microsoft acquired GitHub."
    }
    assert {item["text"] for item in candidate["negated_evidence"]} == {
        "Microsoft did not acquire GitHub."
    }


def test_missing_comparison_contracts_return_404() -> None:
    missing_run = client.get("/api/v1/analyses/run_missing/comparison")
    missing_workspace = client.get("/api/v1/workspaces/ws_missing/comparison/latest")

    assert missing_run.status_code == 404
    assert missing_workspace.status_code == 404
