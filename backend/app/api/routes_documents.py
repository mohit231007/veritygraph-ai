from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.config import get_settings
from app.domain.source import SourceBundle
from app.ingestion.documents import DocumentParseError
from app.repositories.source_repository import get_source_repository
from app.services.document_ingestion import (
    UnsupportedDocumentTypeError,
    UploadTooLargeError,
    UploadValidationError,
    ingest_document_upload,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=SourceBundle,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and parse a document with provenance",
)
async def upload_document(file: Annotated[UploadFile, File(...)]) -> SourceBundle:
    settings = get_settings()
    repository = get_source_repository()

    try:
        return await ingest_document_upload(
            upload=file,
            repository=repository,
            max_upload_bytes=settings.max_upload_bytes,
        )
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except (UploadValidationError, DocumentParseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{source_id}",
    response_model=SourceBundle,
    summary="Retrieve a previously ingested source and its evidence spans",
)
def get_document(source_id: str) -> SourceBundle:
    bundle = get_source_repository().get(source_id)
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    return bundle
