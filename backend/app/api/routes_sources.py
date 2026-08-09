from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.domain.source import SourceBundle, SourceDocument
from app.repositories.source_repository import SourceRepository, get_source_repository

router = APIRouter(prefix="/sources", tags=["sources"])
SourceRepositoryDependency = Annotated[SourceRepository, Depends(get_source_repository)]


@router.get(
    "",
    response_model=list[SourceDocument],
    summary="List persisted canonical sources",
)
def list_sources(
    repository: SourceRepositoryDependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[SourceDocument]:
    return repository.list_documents(limit=limit)


@router.get(
    "/{source_id}",
    response_model=SourceBundle,
    summary="Retrieve one canonical source with evidence spans",
)
def get_source(
    source_id: str,
    repository: SourceRepositoryDependency,
) -> SourceBundle:
    bundle = repository.get(source_id)
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    return bundle
