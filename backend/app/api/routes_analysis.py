from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.domain.analysis import AnalysisRun, WorkspaceAnalysis
from app.nlp.engine import SpacyNlpEngine
from app.repositories.analysis_repository import AnalysisRepository, get_analysis_repository
from app.repositories.source_repository import SourceRepository, get_source_repository
from app.repositories.workspace_repository import WorkspaceRepository, get_workspace_repository
from app.services.analysis import (
    EmptyWorkspaceError,
    WorkspaceAnalysisNotFoundError,
    get_nlp_engine,
    run_workspace_analysis,
)

router = APIRouter(tags=["analysis"])

WorkspaceRepositoryDependency = Annotated[
    WorkspaceRepository,
    Depends(get_workspace_repository),
]
SourceRepositoryDependency = Annotated[SourceRepository, Depends(get_source_repository)]
AnalysisRepositoryDependency = Annotated[
    AnalysisRepository,
    Depends(get_analysis_repository),
]
NlpEngineDependency = Annotated[SpacyNlpEngine, Depends(get_nlp_engine)]


@router.post(
    "/workspaces/{workspace_id}/analyses",
    response_model=WorkspaceAnalysis,
    status_code=status.HTTP_201_CREATED,
    summary="Run the local evidence-linked NLP baseline over a workspace",
)
def analyse_workspace(
    workspace_id: str,
    workspace_repository: WorkspaceRepositoryDependency,
    source_repository: SourceRepositoryDependency,
    analysis_repository: AnalysisRepositoryDependency,
    engine: NlpEngineDependency,
) -> WorkspaceAnalysis:
    try:
        return run_workspace_analysis(
            workspace_id=workspace_id,
            workspace_repository=workspace_repository,
            source_repository=source_repository,
            analysis_repository=analysis_repository,
            engine=engine,
        )
    except WorkspaceAnalysisNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except EmptyWorkspaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/workspaces/{workspace_id}/analyses/latest",
    response_model=WorkspaceAnalysis,
    summary="Retrieve the latest completed workspace analysis",
)
def latest_workspace_analysis(
    workspace_id: str,
    workspace_repository: WorkspaceRepositoryDependency,
    analysis_repository: AnalysisRepositoryDependency,
) -> WorkspaceAnalysis:
    if workspace_repository.get(workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    analysis = analysis_repository.latest_for_workspace(workspace_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No completed analysis found.")
    return analysis


@router.get(
    "/workspaces/{workspace_id}/analyses",
    response_model=list[AnalysisRun],
    summary="List versioned analysis runs for a workspace",
)
def list_workspace_analyses(
    workspace_id: str,
    workspace_repository: WorkspaceRepositoryDependency,
    analysis_repository: AnalysisRepositoryDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AnalysisRun]:
    if workspace_repository.get(workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return analysis_repository.list_runs(workspace_id, limit=limit)


@router.get(
    "/analyses/{run_id}",
    response_model=WorkspaceAnalysis,
    summary="Retrieve one immutable analysis result by run ID",
)
def get_analysis(
    run_id: str,
    analysis_repository: AnalysisRepositoryDependency,
) -> WorkspaceAnalysis:
    analysis = analysis_repository.get(run_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    return analysis
