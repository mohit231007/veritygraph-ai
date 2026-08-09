from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.retrieval import RetrievalPreviewRequest, WorkspaceRetrievalPreview
from app.repositories.source_repository import SourceRepository, get_source_repository
from app.repositories.workspace_repository import (
    WorkspaceRepository,
    get_workspace_repository,
)
from app.services.retrieval import build_workspace_retrieval_preview

router = APIRouter(prefix="/workspaces", tags=["retrieval"])
WorkspaceRepositoryDependency = Annotated[
    WorkspaceRepository,
    Depends(get_workspace_repository),
]
SourceRepositoryDependency = Annotated[
    SourceRepository,
    Depends(get_source_repository),
]


@router.post(
    "/{workspace_id}/retrieval/preview",
    response_model=WorkspaceRetrievalPreview,
    summary="Preview deterministic provenance-first span retrieval",
)
def preview_workspace_retrieval(
    workspace_id: str,
    request: RetrievalPreviewRequest,
    workspace_repository: WorkspaceRepositoryDependency,
    source_repository: SourceRepositoryDependency,
) -> WorkspaceRetrievalPreview:
    workspace = workspace_repository.get(workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )
    return build_workspace_retrieval_preview(
        workspace,
        query=request.query,
        limit=request.limit,
        source_repository=source_repository,
    )
