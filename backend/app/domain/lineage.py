from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.source import BibliographicIdentifierKind, IdentifierObservationRole


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
    reference_text: str | None = None
    citation_label: str | None = None
    citation_marker: str | None = None
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


class IdentifierMatchResolution(StrEnum):
    NO_WORKSPACE_MATCH = "no_workspace_match"
    WORKSPACE_UNIQUE = "workspace_unique"
    WORKSPACE_AMBIGUOUS = "workspace_ambiguous"


class IdentifierLineageObservation(BaseModel):
    identifier_id: str
    source_id: str
    source_label: str
    kind: BibliographicIdentifierKind
    raw_value: str
    normalized_value: str
    role: IdentifierObservationRole
    version: int | None = Field(default=None, ge=1)
    span_id: str | None = None
    reference_id: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    paragraph_number: int | None = Field(default=None, ge=1)
    resolution: IdentifierMatchResolution
    matching_source_ids: list[str] = Field(default_factory=list)
    matching_labels: list[str] = Field(default_factory=list)
    identity_target_resolution: IdentifierMatchResolution
    identity_target_source_ids: list[str] = Field(default_factory=list)
    identity_target_labels: list[str] = Field(default_factory=list)
    context_text: str | None = None
    extraction_method: str


class IdentifierLineageSummary(BaseModel):
    source_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    unique_identifier_count: int = Field(ge=0)
    matched_observation_count: int = Field(ge=0)
    ambiguous_observation_count: int = Field(ge=0)
    reference_linked_observation_count: int = Field(ge=0)
    source_identity_observation_count: int = Field(ge=0)
    resolved_identity_target_observation_count: int = Field(ge=0)
    ambiguous_identity_target_observation_count: int = Field(ge=0)


class WorkspaceIdentifierLineage(BaseModel):
    workspace_id: str
    lineage_version: str
    summary: IdentifierLineageSummary
    identifiers: list[IdentifierLineageObservation]
    interpretation_note: str
