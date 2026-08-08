from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    """Origin category for content entering the VerityGraph pipeline."""

    DOCUMENT = "document"
    WIKIPEDIA = "wikipedia"
    PUBLIC_URL = "public_url"


class SourceDocument(BaseModel):
    """Canonical metadata shared by every VerityGraph source."""

    source_id: str
    source_type: SourceType
    title: str
    filename: str | None = None
    source_format: str
    mime_type: str
    content_hash: str
    size_bytes: int = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class SourceSpan(BaseModel):
    """A traceable text span extracted from a source document.

    ``char_start`` and ``char_end`` refer to VerityGraph's normalized extracted
    corpus for this source, not byte offsets inside the original binary file.
    """

    span_id: str
    source_id: str
    text: str
    page_number: int | None = Field(default=None, ge=1)
    section: str | None = None
    paragraph_number: int | None = Field(default=None, ge=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)


class SourceBundle(BaseModel):
    """Canonical ingestion result returned by the API and persisted by repositories."""

    document: SourceDocument
    spans: list[SourceSpan]

    @property
    def extracted_text(self) -> str:
        return "\n\n".join(span.text for span in self.spans)
