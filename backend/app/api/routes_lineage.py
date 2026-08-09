from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.lineage import WorkspaceReferenceLineage
from app.repositories.source_repository import SourceRepository, get_source_repository
from app.repositories.workspace_repository import (
    WorkspaceRepository,
    get_workspace_repository,
)
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
    workspace = workspace_repository.get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return build_workspace_reference_lineage(
        workspace,
        source_repository=source_repository,
    )
