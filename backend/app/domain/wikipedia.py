from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class WikipediaSearchResult(BaseModel):
    page_id: int
    title: str
    snippet: str = ""
    word_count: int = Field(default=0, ge=0)
    size_bytes: int = Field(default=0, ge=0)
    updated_at: datetime | None = None


class WikipediaSection(BaseModel):
    index: str
    title: str
    number: str = ""
    level: int = Field(default=1, ge=1)
    anchor: str = ""


class WikipediaOutline(BaseModel):
    page_id: int
    title: str
    revision_id: int | None = None
    url: str
    sections: list[WikipediaSection]


class WikipediaImportRequest(BaseModel):
    page_id: int = Field(gt=0)
    section_indices: list[str] = Field(min_length=1, max_length=25)

    @field_validator("section_indices")
    @classmethod
    def validate_section_indices(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or not normalized.isdigit():
                raise ValueError("section indices must be non-negative integer strings")
            if normalized not in seen:
                cleaned.append(normalized)
                seen.add(normalized)
        if not cleaned:
            raise ValueError("at least one section is required")
        return cleaned


class WikipediaFetchedReference(BaseModel):
    target_url: str
    anchor_text: str | None = None
    context_text: str | None = None
    citation_label: str | None = None
    citation_marker: str | None = None
    extraction_method: str


class WikipediaFetchedSection(BaseModel):
    index: str
    title: str
    paragraphs: list[str]
    references: list[WikipediaFetchedReference] = Field(default_factory=list)


class WikipediaFetchedPage(BaseModel):
    page_id: int
    title: str
    revision_id: int | None = None
    url: str
    sections: list[WikipediaFetchedSection]
