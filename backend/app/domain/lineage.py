from __future__ import annotations

from pydantic import BaseModel, Field


class ReferenceLineageEdge(BaseModel):
    reference_id: str
    source_id: str
    source_label: str
    span_id: str | None = None
    target_url: str
    normalized_target_url: str
    target_source_id: str | None = None
    target_label: str | None = None
    anchor_text: str | None = None
    context_text: str | None = None
    extraction_method: str
    resolved_to_workspace_source: bool = False
    self_reference: bool = False


class ReferenceLineageSummary(BaseModel):
    source_count: int = Field(ge=0)
    reference_count: int = Field(ge=0)
    resolved_workspace_reference_count: int = Field(ge=0)
    external_reference_count: int = Field(ge=0)
    self_reference_count: int = Field(ge=0)


class WorkspaceReferenceLineage(BaseModel):
    workspace_id: str
    lineage_version: str
    summary: ReferenceLineageSummary
    references: list[ReferenceLineageEdge]
    interpretation_note: str
