from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.domain.graph import EvidenceGraph, GraphPath
from app.repositories.analysis_repository import AnalysisRepository, get_analysis_repository
from app.repositories.workspace_repository import WorkspaceRepository, get_workspace_repository
from app.services.graph import (
    GraphPathNotFoundError,
    build_evidence_graph,
    shortest_connection_path,
)

router = APIRouter(tags=["graph"])

AnalysisRepositoryDependency = Annotated[
    AnalysisRepository,
    Depends(get_analysis_repository),
]
WorkspaceRepositoryDependency = Annotated[
    WorkspaceRepository,
    Depends(get_workspace_repository),
]


@router.get(
    "/analyses/{run_id}/graph",
    response_model=EvidenceGraph,
    summary="Project one immutable analysis run into an evidence graph",
)
def analysis_graph(
    run_id: str,
    analysis_repository: AnalysisRepositoryDependency,
) -> EvidenceGraph:
    analysis = analysis_repository.get(run_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    return build_evidence_graph(analysis)


@router.get(
    "/workspaces/{workspace_id}/graph/latest",
    response_model=EvidenceGraph,
    summary="Project the latest completed workspace analysis into an evidence graph",
)
def latest_workspace_graph(
    workspace_id: str,
    workspace_repository: WorkspaceRepositoryDependency,
    analysis_repository: AnalysisRepositoryDependency,
) -> EvidenceGraph:
    if workspace_repository.get(workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    analysis = analysis_repository.latest_for_workspace(workspace_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed analysis found for this workspace.",
        )
    return build_evidence_graph(analysis)


@router.get(
    "/analyses/{run_id}/graph/path",
    response_model=GraphPath,
    summary="Find the fewest-hop undirected connection path between two entities",
)
def graph_path(
    run_id: str,
    analysis_repository: AnalysisRepositoryDependency,
    source_entity_id: Annotated[str, Query(min_length=1)],
    target_entity_id: Annotated[str, Query(min_length=1)],
) -> GraphPath:
    analysis = analysis_repository.get(run_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    try:
        return shortest_connection_path(
            analysis,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
        )
    except GraphPathNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
