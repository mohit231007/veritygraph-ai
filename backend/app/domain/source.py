from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


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
    url: str | None = None
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

    @model_validator(mode="after")
    def validate_offsets(self) -> SourceSpan:
        if self.char_end < self.char_start:
            raise ValueError("char_end must be greater than or equal to char_start")
        return self


class SourceReference(BaseModel):
    """One explicit URL reference retained with exact source provenance.

    References are observations, not causal claims. ``span_id`` is populated only
    when the reference can be tied to retained evidence text deterministically.
    Page/paragraph locators are format provenance and do not imply that the target
    URL itself was present in extracted NLP text. ``reference_text`` can preserve a
    bibliographic or footnote entry separately from the citing span context.
    Citation marker fields preserve an explicit source-format bridge such as a
    MediaWiki ``[1]`` marker without assigning citation intent or truth semantics.
    """

    reference_id: str
    source_id: str
    span_id: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    paragraph_number: int | None = Field(default=None, ge=1)
    target_url: str
    normalized_target_url: str
    anchor_text: str | None = None
    context_text: str | None = None
    reference_text: str | None = None
    citation_label: str | None = None
    citation_marker: str | None = None
    extraction_method: str


class SourceBundle(BaseModel):
    """Canonical ingestion result returned by the API and persisted by repositories."""

    document: SourceDocument
    spans: list[SourceSpan]
    references: list[SourceReference] = Field(default_factory=list)

    @property
    def extracted_text(self) -> str:
        return "\n\n".join(span.text for span in self.spans)
