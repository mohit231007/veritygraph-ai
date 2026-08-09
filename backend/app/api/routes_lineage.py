from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.citations import WorkspaceCitationGraph
from app.domain.lineage import WorkspaceIdentifierLineage, WorkspaceReferenceLineage
from app.repositories.source_repository import SourceRepository, get_source_repository
from app.repositories.workspace_repository import (
    WorkspaceRepository,
    get_workspace_repository,
)
from app.services.citation_graph import build_workspace_citation_graph
from app.services.identifier_lineage import build_workspace_identifier_lineage
from app.services.reference_lineage import build_workspace_reference_lineage

router = APIRouter(prefix="/workspaces", tags=["reference-lineage"])
WorkspaceRepositoryDependency = Annotated[
    WorkspaceRepository,
    Depends(get_workspace_repository),
]
SourceRepositoryDependency = Annotated[
    SourceRepository,
    Depends(get_source_repository),
]


def _workspace_or_404(
    workspace_id: str,
    repository: WorkspaceRepository,
):
    workspace = repository.get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return workspace


@router.get(
    "/{workspace_id}/reference-lineage",
    response_model=WorkspaceReferenceLineage,
    summary="Project explicit URL reference lineage for a workspace",
)
def get_workspace_reference_lineage(
    workspace_id: str,
    workspace_repository: WorkspaceRepositoryDependency,
    source_repository: SourceRepositoryDependency,
) -> WorkspaceReferenceLineage:
    workspace = _workspace_or_404(workspace_id, workspace_repository)
    return build_workspace_reference_lineage(
        workspace,
        source_repository=source_repository,
    )


@router.get(
    "/{workspace_id}/identifier-lineage",
    response_model=WorkspaceIdentifierLineage,
    summary="Project bibliographic observations and attested source identities",
)
def get_workspace_identifier_lineage(
    workspace_id: str,
    workspace_repository: WorkspaceRepositoryDependency,
    source_repository: SourceRepositoryDependency,
) -> WorkspaceIdentifierLineage:
    workspace = _workspace_or_404(workspace_id, workspace_repository)
    return build_workspace_identifier_lineage(
        workspace,
        source_repository=source_repository,
    )


@router.get(
    "/{workspace_id}/citation-graph",
    response_model=WorkspaceCitationGraph,
    summary="Project uniquely resolved explicit citation and reference edges",
)
def get_workspace_citation_graph(
    workspace_id: str,
    workspace_repository: WorkspaceRepositoryDependency,
    source_repository: SourceRepositoryDependency,
) -> WorkspaceCitationGraph:
    workspace = _workspace_or_404(workspace_id, workspace_repository)
    return build_workspace_citation_graph(
        workspace,
        source_repository=source_repository,
    )
