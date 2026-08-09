from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ReferenceResolution(StrEnum):
    EXTERNAL = "external"
    WORKSPACE_UNIQUE = "workspace_unique"
    WORKSPACE_AMBIGUOUS = "workspace_ambiguous"


class ReferenceLineageEdge(BaseModel):
    reference_id: str
    source_id: str
    source_label: str
    span_id: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    paragraph_number: int | None = Field(default=None, ge=1)
    target_url: str
    normalized_target_url: str
    resolution: ReferenceResolution
    target_source_ids: list[str] = Field(default_factory=list)
    target_labels: list[str] = Field(default_factory=list)
    anchor_text: str | None = None
    context_text: str | None = None
    extraction_method: str
    self_reference: bool = False


class ReferenceLineageSummary(BaseModel):
    source_count: int = Field(ge=0)
    reference_count: int = Field(ge=0)
    resolved_workspace_reference_count: int = Field(ge=0)
    ambiguous_workspace_reference_count: int = Field(ge=0)
    external_reference_count: int = Field(ge=0)
    self_reference_count: int = Field(ge=0)


class WorkspaceReferenceLineage(BaseModel):
    workspace_id: str
    lineage_version: str
    summary: ReferenceLineageSummary
    references: list[ReferenceLineageEdge]
    interpretation_note: str
