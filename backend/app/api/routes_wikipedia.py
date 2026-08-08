from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.domain.source import SourceBundle
from app.domain.wikipedia import WikipediaImportRequest, WikipediaOutline, WikipediaSearchResult
from app.ingestion.wikipedia import (
    WikipediaPageNotFoundError,
    WikipediaProvider,
    WikipediaProviderError,
)
from app.repositories.source_repository import get_source_repository
from app.services.wikipedia_ingestion import get_wikipedia_provider, ingest_wikipedia_sections

router = APIRouter(prefix="/wikipedia", tags=["wikipedia"])
WikipediaProviderDependency = Annotated[WikipediaProvider, Depends(get_wikipedia_provider)]


@router.get(
    "/search",
    response_model=list[WikipediaSearchResult],
    summary="Search Wikipedia using the official MediaWiki API",
)
async def search_wikipedia(
    provider: WikipediaProviderDependency,
    q: Annotated[str, Query(min_length=2, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=10)] = 6,
) -> list[WikipediaSearchResult]:
    try:
        return await provider.search(q.strip(), limit)
    except WikipediaProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get(
    "/pages/{page_id}/outline",
    response_model=WikipediaOutline,
    summary="Preview a Wikipedia page and its selectable sections",
)
async def wikipedia_outline(
    page_id: int,
    provider: WikipediaProviderDependency,
) -> WikipediaOutline:
    try:
        return await provider.outline(page_id)
    except WikipediaPageNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WikipediaProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post(
    "/import",
    response_model=SourceBundle,
    status_code=status.HTTP_201_CREATED,
    summary="Import selected Wikipedia sections into canonical provenance",
)
async def import_wikipedia(
    request: WikipediaImportRequest,
    provider: WikipediaProviderDependency,
) -> SourceBundle:
    try:
        return await ingest_wikipedia_sections(
            page_id=request.page_id,
            section_indices=request.section_indices,
            provider=provider,
            repository=get_source_repository(),
        )
    except WikipediaPageNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (WikipediaProviderError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
