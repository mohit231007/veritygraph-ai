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


def create_analysed_workspace() -> tuple[str, dict]:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Graph API workspace"},
    ).json()
    source = client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "graph.txt",
                b"Microsoft acquired GitHub in 2018.",
                "text/plain",
            )
        },
    ).json()
    source_id = source["document"]["source_id"]
    added = client.put(
        f"/api/v1/workspaces/{workspace['workspace_id']}/sources/{source_id}"
    )
    assert added.status_code == 200
    analysis = client.post(
        f"/api/v1/workspaces/{workspace['workspace_id']}/analyses"
    )
    assert analysis.status_code == 201
    return workspace["workspace_id"], analysis.json()


def test_graph_api_projects_latest_and_specific_analysis_run() -> None:
    workspace_id, analysis = create_analysed_workspace()
    run_id = analysis["run"]["run_id"]

    latest = client.get(f"/api/v1/workspaces/{workspace_id}/graph/latest")
    by_run = client.get(f"/api/v1/analyses/{run_id}/graph")

    assert latest.status_code == 200
    assert by_run.status_code == 200
    assert latest.json() == by_run.json()
    graph = latest.json()
    assert graph["run_id"] == run_id
    assert graph["graph_version"] == "evidence-graph-v2-polarity"
    assert graph["summary"]["node_count"] >= 2
    assert graph["summary"]["edge_count"] >= 1
    edge = next(edge for edge in graph["edges"] if edge["predicate"] == "acquire")
    assert edge["polarity"] == "affirmed"
    assert edge["polarity_method"] == "dependency_no_root_negation_v1"


def test_graph_path_api_returns_relation_linked_hop() -> None:
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
    path = response.json()
    assert path["directed"] is False
    assert path["hop_count"] == 1
    assert path["entity_ids"] == [names["Microsoft"], names["GitHub"]]
    assert len(path["steps"][0]["relation_ids"]) >= 1


def test_graph_api_requires_existing_completed_analysis() -> None:
    missing_run = client.get("/api/v1/analyses/run_missing/graph")
    missing_workspace = client.get("/api/v1/workspaces/ws_missing/graph/latest")

    assert missing_run.status_code == 404
    assert missing_workspace.status_code == 404
