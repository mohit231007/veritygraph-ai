from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.source import SourceBundle
from app.domain.web import PublicUrlImportRequest
from app.ingestion.web import (
    UnsafeUrlError,
    UnsupportedWebContentError,
    WebContentTooLargeError,
    WebFetcher,
    WebFetchError,
)
from app.repositories.source_repository import get_source_repository
from app.services.web_ingestion import WebExtractionError, get_web_fetcher, ingest_public_url

router = APIRouter(prefix="/web", tags=["web"])
WebFetcherDependency = Annotated[WebFetcher, Depends(get_web_fetcher)]


@router.post(
    "/import",
    response_model=SourceBundle,
    status_code=status.HTTP_201_CREATED,
    summary="Safely import a permitted public HTTP(S) page",
)
async def import_public_url(
    request: PublicUrlImportRequest,
    fetcher: WebFetcherDependency,
) -> SourceBundle:
    try:
        return await ingest_public_url(
            url=request.url,
            fetcher=fetcher,
            repository=get_source_repository(),
        )
    except UnsafeUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except UnsupportedWebContentError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except WebContentTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except WebExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except WebFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
