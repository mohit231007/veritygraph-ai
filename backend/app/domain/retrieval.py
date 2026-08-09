from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from app.domain.citations import CitationMechanism


class RetrievalPreviewRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=8, ge=1, le=25)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if len(normalized) < 2:
            raise ValueError("query must contain at least two non-whitespace characters")
        return normalized


class RetrievalHit(BaseModel):
    rank: int = Field(ge=1)
    source_id: str
    source_label: str
    span_id: str
    text: str
    page_number: int | None = Field(default=None, ge=1)
    section: str | None = None
    paragraph_number: int | None = Field(default=None, ge=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    score: float = Field(ge=0)
    matched_terms: list[str] = Field(default_factory=list)


class CitationContextDirection(StrEnum):
    OUTGOING = "outgoing"
    INCOMING = "incoming"


class RetrievalCitationContext(BaseModel):
    edge_id: str
    seed_source_id: str
    seed_source_label: str
    direction: CitationContextDirection
    neighbor_source_id: str
    neighbor_label: str
    mechanisms: list[CitationMechanism]
    evidence_count: int = Field(ge=1)


class RetrievalPreviewSummary(BaseModel):
    workspace_source_count: int = Field(ge=0)
    indexed_span_count: int = Field(ge=0)
    query_term_count: int = Field(ge=0)
    direct_hit_count: int = Field(ge=0)
    direct_hit_source_count: int = Field(ge=0)
    citation_context_count: int = Field(ge=0)


class WorkspaceRetrievalPreview(BaseModel):
    workspace_id: str
    retrieval_version: str
    query: str
    summary: RetrievalPreviewSummary
    hits: list[RetrievalHit]
    citation_context: list[RetrievalCitationContext]
    interpretation_note: str
