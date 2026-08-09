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


def create_workspace(name: str) -> str:
    return client.post("/api/v1/workspaces", json={"name": name}).json()["workspace_id"]


def test_comparison_api_uses_exact_qualified_support() -> None:
    workspace_id = create_workspace("Corroboration workspace")
    first_source_id = upload_and_add(
        workspace_id,
        "source-one.txt",
        "Microsoft acquired GitHub in 2018. GitHub acquired OpenAI.",
    )
    second_source_id = upload_and_add(
        workspace_id,
        "source-two.txt",
        "Microsoft acquired GitHub in 2018. Amazon acquired Twitch.",
    )

    analysis_response = client.post(f"/api/v1/workspaces/{workspace_id}/analyses")
    assert analysis_response.status_code == 201
    run = analysis_response.json()["run"]
    assert run["source_ids"] == [first_source_id, second_source_id]

    comparison = client.get(f"/api/v1/analyses/{run['run_id']}/comparison").json()
    assert comparison["comparison_version"] == "source-corroboration-v4-relationships"
    assert comparison["summary"]["cross_source_claim_count"] >= 1
    assert comparison["summary"]["contradiction_candidate_count"] == 0
    assert comparison["summary"]["exact_content_match_pair_count"] == 0
    assert comparison["summary"]["exact_evidence_overlap_pair_count"] == 1
    assert comparison["summary"]["possible_derivation_pair_count"] == 1

    microsoft_github = next(
        claim
        for claim in comparison["claims"]
        if claim["subject_label"] == "Microsoft"
        and claim["predicate"] == "acquire"
        and claim["object_label"] == "GitHub"
    )
    assert microsoft_github["polarity"] == "affirmed"
    assert microsoft_github["modality"] == "asserted"
    assert microsoft_github["temporal_years"] == [2018]
    assert microsoft_github["support_level"] == "cross_source"
    assert set(microsoft_github["source_ids"]) == {first_source_id, second_source_id}
    assert microsoft_github["distinct_content_fingerprint_count"] == 2
    assert microsoft_github["distinct_evidence_text_count"] == 1

    signal = comparison["source_relationships"][0]
    assert {signal["left_source_id"], signal["right_source_id"]} == {
        first_source_id,
        second_source_id,
    }
    assert signal["exact_content_fingerprint_match"] is False
    assert signal["exact_evidence_text_overlap_count"] == 1
    assert signal["possible_derivation_signal"] is True
    assert (
        "identical normalized supporting sentence on a shared resolved assertion"
        in signal["review_reasons"]
    )
    assert "does not prove independent reporting" in comparison["interpretation_note"]
    assert "absence does not prove independence" in comparison["interpretation_note"]


def test_comparison_api_detects_same_year_asserted_negation() -> None:
    workspace_id = create_workspace("Same year contradiction")
    affirmed_source_id = upload_and_add(
        workspace_id, "affirmed.txt", "Microsoft acquired GitHub in 2018."
    )
    negated_source_id = upload_and_add(
        workspace_id, "negated.txt", "Microsoft did not acquire GitHub in 2018."
    )

    run_id = client.post(f"/api/v1/workspaces/{workspace_id}/analyses").json()["run"]["run_id"]
    comparison = client.get(f"/api/v1/analyses/{run_id}/comparison").json()

    assert comparison["summary"]["contradiction_candidate_count"] == 1
    candidate = comparison["contradictions"][0]
    assert candidate["temporal_years"] == [2018]
    assert candidate["affirmed_source_ids"] == [affirmed_source_id]
    assert candidate["negated_source_ids"] == [negated_source_id]


def test_comparison_api_rejects_disjoint_year_and_modal_false_conflicts() -> None:
    workspace_id = create_workspace("Qualifier guardrail")
    upload_and_add(workspace_id, "past.txt", "Microsoft acquired GitHub in 2018.")
    upload_and_add(workspace_id, "later.txt", "Microsoft did not acquire GitHub in 2019.")
    upload_and_add(workspace_id, "future.txt", "Microsoft may acquire OpenAI in 2027.")
    upload_and_add(workspace_id, "future-no.txt", "Microsoft did not acquire OpenAI in 2027.")

    run_id = client.post(f"/api/v1/workspaces/{workspace_id}/analyses").json()["run"]["run_id"]
    comparison = client.get(f"/api/v1/analyses/{run_id}/comparison").json()

    assert comparison["summary"]["contradiction_candidate_count"] == 0
    assert comparison["contradictions"] == []
    assert "asserted opposing polarity" in comparison["interpretation_note"]
    assert "compatible explicit time scope" in comparison["interpretation_note"]


def test_missing_comparison_contracts_return_404() -> None:
    assert client.get("/api/v1/analyses/run_missing/comparison").status_code == 404
    assert client.get("/api/v1/workspaces/ws_missing/comparison/latest").status_code == 404
