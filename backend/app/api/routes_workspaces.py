from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.domain.workspace import WorkspaceCreate, WorkspaceDetail, WorkspaceSummary
from app.repositories.workspace_repository import (
    WorkspaceNotFoundError,
    WorkspaceRepository,
    WorkspaceSourceNotFoundError,
    get_workspace_repository,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
WorkspaceRepositoryDependency = Annotated[
    WorkspaceRepository,
    Depends(get_workspace_repository),
]


@router.post(
    "",
    response_model=WorkspaceDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a persistent multi-source research workspace",
)
def create_workspace(
    request: WorkspaceCreate,
    repository: WorkspaceRepositoryDependency,
) -> WorkspaceDetail:
    return repository.create(request)


@router.get(
    "",
    response_model=list[WorkspaceSummary],
    summary="List persistent research workspaces",
)
def list_workspaces(
    repository: WorkspaceRepositoryDependency,
) -> list[WorkspaceSummary]:
    return repository.list()


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceDetail,
    summary="Retrieve one workspace and its canonical source metadata",
)
def get_workspace(
    workspace_id: str,
    repository: WorkspaceRepositoryDependency,
) -> WorkspaceDetail:
    workspace = repository.get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return workspace


@router.put(
    "/{workspace_id}/sources/{source_id}",
    response_model=WorkspaceDetail,
    summary="Add a canonical source to a workspace idempotently",
)
def add_workspace_source(
    workspace_id: str,
    source_id: str,
    repository: WorkspaceRepositoryDependency,
) -> WorkspaceDetail:
    try:
        return repository.add_source(workspace_id, source_id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        ) from exc
    except WorkspaceSourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        ) from exc


@router.delete(
    "/{workspace_id}/sources/{source_id}",
    response_model=WorkspaceDetail,
    summary="Remove a source from a workspace without deleting the source",
)
def remove_workspace_source(
    workspace_id: str,
    source_id: str,
    repository: WorkspaceRepositoryDependency,
) -> WorkspaceDetail:
    try:
        return repository.remove_source(workspace_id, source_id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        ) from exc


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a workspace without deleting its source records",
)
def delete_workspace(
    workspace_id: str,
    repository: WorkspaceRepositoryDependency,
) -> Response:
    if not repository.delete(workspace_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
