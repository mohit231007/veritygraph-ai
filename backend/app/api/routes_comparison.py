from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.analysis import WorkspaceAnalysis
from app.domain.comparison import SourceComparison
from app.domain.source import SourceDocument
from app.repositories.analysis_repository import AnalysisRepository, get_analysis_repository
from app.repositories.source_repository import SourceRepository, get_source_repository
from app.repositories.workspace_repository import WorkspaceRepository, get_workspace_repository
from app.services.comparison import build_source_comparison

router = APIRouter(tags=["comparison"])

AnalysisRepositoryDependency = Annotated[
    AnalysisRepository,
    Depends(get_analysis_repository),
]
SourceRepositoryDependency = Annotated[SourceRepository, Depends(get_source_repository)]
WorkspaceRepositoryDependency = Annotated[
    WorkspaceRepository,
    Depends(get_workspace_repository),
]


def _source_documents(
    analysis: WorkspaceAnalysis,
    source_repository: SourceRepository,
) -> dict[str, SourceDocument]:
    source_ids = list(analysis.run.source_ids)
    source_ids.extend(
        evidence.source_id
        for relation in analysis.relations
        for evidence in relation.evidence
    )
    source_ids.extend(
        mention.source_id
        for entity in analysis.entities
        for mention in entity.mentions
    )

    documents: dict[str, SourceDocument] = {}
    for source_id in dict.fromkeys(source_ids):
        bundle = source_repository.get(source_id)
        if bundle is not None:
            documents[source_id] = bundle.document
    return documents


@router.get(
    "/analyses/{run_id}/comparison",
    response_model=SourceComparison,
    summary="Compare exact claim support across the sources in one analysis run",
)
def analysis_source_comparison(
    run_id: str,
    analysis_repository: AnalysisRepositoryDependency,
    source_repository: SourceRepositoryDependency,
) -> SourceComparison:
    analysis = analysis_repository.get(run_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found.")
    return build_source_comparison(
        analysis,
        source_documents=_source_documents(analysis, source_repository),
    )


@router.get(
    "/workspaces/{workspace_id}/comparison/latest",
    response_model=SourceComparison,
    summary="Compare source support in the latest completed workspace analysis",
)
def latest_workspace_source_comparison(
    workspace_id: str,
    workspace_repository: WorkspaceRepositoryDependency,
    analysis_repository: AnalysisRepositoryDependency,
    source_repository: SourceRepositoryDependency,
) -> SourceComparison:
    if workspace_repository.get(workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    analysis = analysis_repository.latest_for_workspace(workspace_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed analysis found for this workspace.",
        )
    return build_source_comparison(
        analysis,
        source_documents=_source_documents(analysis, source_repository),
    )
