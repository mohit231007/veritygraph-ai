import pytest
from app.main import app
from app.repositories.analysis_repository import get_analysis_repository
from app.repositories.source_repository import get_source_repository
from app.repositories.workspace_repository import get_workspace_repository
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_graph_api_state() -> None:
    get_analysis_repository().clear()
    get_workspace_repository().clear()
    get_source_repository().clear()
    yield
    get_analysis_repository().clear()
    get_workspace_repository().clear()
    get_source_repository().clear()


def create_analysed_workspace(text: str = "Microsoft acquired GitHub in 2018.") -> tuple[str, dict]:
    workspace = client.post(
        "/api/v1/workspaces", json={"name": "Graph API workspace"}
    ).json()
    source = client.post(
        "/api/v1/documents/upload",
        files={"file": ("graph.txt", text.encode("utf-8"), "text/plain")},
    ).json()
    source_id = source["document"]["source_id"]
    added = client.put(
        f"/api/v1/workspaces/{workspace['workspace_id']}/sources/{source_id}"
    )
    assert added.status_code == 200
    analysis = client.post(f"/api/v1/workspaces/{workspace['workspace_id']}/analyses")
    assert analysis.status_code == 201
    return workspace["workspace_id"], analysis.json()


def test_graph_api_projects_qualified_analysis_run() -> None:
    workspace_id, analysis = create_analysed_workspace()
    run_id = analysis["run"]["run_id"]

    latest = client.get(f"/api/v1/workspaces/{workspace_id}/graph/latest")
    by_run = client.get(f"/api/v1/analyses/{run_id}/graph")

    assert latest.status_code == 200
    assert latest.json() == by_run.json()
    graph = latest.json()
    assert graph["graph_version"] == "evidence-graph-v3-qualifiers"
    edge = next(edge for edge in graph["edges"] if edge["predicate"] == "acquire")
    assert edge["polarity"] == "affirmed"
    assert edge["modality"] == "asserted"
    assert edge["temporal_years"] == [2018]


def test_graph_path_api_returns_established_relation_hop() -> None:
    _workspace_id, analysis = create_analysed_workspace()
    run_id = analysis["run"]["run_id"]
    names = {entity["canonical_name"]: entity["entity_id"] for entity in analysis["entities"]}

    response = client.get(
        f"/api/v1/analyses/{run_id}/graph/path",
        params={
            "source_entity_id": names["Microsoft"],
            "target_entity_id": names["GitHub"],
        },
    )
    assert response.status_code == 200
    assert response.json()["hop_count"] == 1


def test_modal_assertion_is_visible_but_cannot_create_graph_path() -> None:
    _workspace_id, analysis = create_analysed_workspace(
        "Microsoft may acquire GitHub in 2027."
    )
    run_id = analysis["run"]["run_id"]
    names = {entity["canonical_name"]: entity["entity_id"] for entity in analysis["entities"]}
    graph = client.get(f"/api/v1/analyses/{run_id}/graph").json()
    edge = next(edge for edge in graph["edges"] if edge["predicate"] == "acquire")
    assert edge["modality"] == "modal"
    assert edge["temporal_years"] == [2027]
    assert graph["summary"]["density"] == 0.0

    path = client.get(
        f"/api/v1/analyses/{run_id}/graph/path",
        params={
            "source_entity_id": names["Microsoft"],
            "target_entity_id": names["GitHub"],
        },
    )
    assert path.status_code == 404


def test_graph_api_requires_existing_completed_analysis() -> None:
    assert client.get("/api/v1/analyses/run_missing/graph").status_code == 404
    assert client.get("/api/v1/workspaces/ws_missing/graph/latest").status_code == 404
