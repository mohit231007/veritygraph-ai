from __future__ import annotations

from hashlib import sha256
from pathlib import PurePosixPath
from uuid import uuid4

from fastapi import UploadFile

from app.domain.source import SourceBundle, SourceDocument, SourceType
from app.ingestion.documents import PARSERS
from app.repositories.source_repository import SourceRepository


class UploadValidationError(ValueError):
    """Raised when an upload violates VerityGraph's input contract."""


class UnsupportedDocumentTypeError(UploadValidationError):
    """Raised when extension or MIME type is not allowed."""


class UploadTooLargeError(UploadValidationError):
    """Raised when a file exceeds the configured upload limit."""


ALLOWED_MIME_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    ".txt": {"text/plain", "application/octet-stream"},
}


def _safe_filename(filename: str | None) -> str:
    candidate = (filename or "").replace("\\", "/")
    safe = PurePosixPath(candidate).name.strip()
    if not safe or safe in {".", ".."}:
        raise UploadValidationError("A valid filename is required.")
    return safe


async def ingest_document_upload(
    *,
    upload: UploadFile,
    repository: SourceRepository,
    max_upload_bytes: int,
) -> SourceBundle:
    """Validate, parse and persist one user-provided document."""

    filename = _safe_filename(upload.filename)
    extension = PurePosixPath(filename).suffix.lower()
    if extension not in PARSERS:
        raise UnsupportedDocumentTypeError("Unsupported document type. Use PDF, DOCX or TXT.")

    mime_type = upload.content_type or "application/octet-stream"
    if mime_type not in ALLOWED_MIME_TYPES[extension]:
        raise UnsupportedDocumentTypeError(
            f"Content type {mime_type!r} is not valid for a {extension} document."
        )

    try:
        content = await upload.read(max_upload_bytes + 1)
    finally:
        await upload.close()

    if not content:
        raise UploadValidationError("The uploaded document is empty.")
    if len(content) > max_upload_bytes:
        raise UploadTooLargeError(
            f"Document exceeds the {max_upload_bytes // (1024 * 1024)} MB upload limit."
        )

    source_id = f"src_{uuid4().hex}"
    spans = PARSERS[extension](source_id, content)

    document = SourceDocument(
        source_id=source_id,
        source_type=SourceType.DOCUMENT,
        title=PurePosixPath(filename).stem or filename,
        filename=filename,
        source_format=extension.removeprefix("."),
        mime_type=mime_type,
        content_hash=sha256(content).hexdigest(),
        size_bytes=len(content),
        metadata={
            "span_count": len(spans),
            "page_count": max(
                (span.page_number or 0 for span in spans),
                default=0,
            ),
        },
    )
    return repository.save(SourceBundle(document=document, spans=spans))
