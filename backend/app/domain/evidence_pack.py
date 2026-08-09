from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.retrieval import RetrievalCitationContext


class EvidencePackRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    max_excerpts: int = Field(default=8, ge=1, le=20)
    max_excerpts_per_source: int = Field(default=3, ge=1, le=10)
    max_chars_per_excerpt: int = Field(default=1200, ge=120, le=5000)
    max_total_chars: int = Field(default=6000, ge=500, le=30000)


class EvidenceExcerpt(BaseModel):
    rank: int = Field(ge=1)
    source_id: str
    source_label: str
    span_id: str
    page_number: int | None = Field(default=None, ge=1)
    section: str | None = None
    paragraph_number: int | None = Field(default=None, ge=1)
    span_char_start: int = Field(ge=0)
    span_char_end: int = Field(ge=0)
    excerpt_char_start: int = Field(ge=0)
    excerpt_char_end: int = Field(ge=0)
    text: str
    score: float = Field(ge=0)
    matched_terms: list[str]
    truncated_before: bool
    truncated_after: bool


class EvidencePackSummary(BaseModel):
    workspace_source_count: int = Field(ge=0)
    indexed_span_count: int = Field(ge=0)
    candidate_hit_count: int = Field(ge=0)
    selected_excerpt_count: int = Field(ge=0)
    selected_source_count: int = Field(ge=0)
    selected_char_count: int = Field(ge=0)
    skipped_by_source_cap: int = Field(ge=0)
    skipped_by_budget: int = Field(ge=0)
    citation_context_count: int = Field(ge=0)


class GroundedEvidencePack(BaseModel):
    workspace_id: str
    pack_version: str
    retrieval_version: str
    query: str
    summary: EvidencePackSummary
    excerpts: list[EvidenceExcerpt]
    citation_context: list[RetrievalCitationContext]
    interpretation_note: str
