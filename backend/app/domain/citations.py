from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.source import SourceType


class CitationMechanism(StrEnum):
    URL_REFERENCE = "url_reference"
    BIBLIOGRAPHIC_IDENTIFIER = "bibliographic_identifier"


class CitationGraphNode(BaseModel):
    source_id: str
    label: str
    source_type: SourceType
    incoming_edge_count: int = Field(ge=0)
    outgoing_edge_count: int = Field(ge=0)


class CitationGraphEdge(BaseModel):
    edge_id: str
    source_id: str
    source_label: str
    target_source_id: str
    target_label: str
    mechanisms: list[CitationMechanism]
    url_reference_ids: list[str] = Field(default_factory=list)
    identifier_ids: list[str] = Field(default_factory=list)
    bibliographic_identities: list[str] = Field(default_factory=list)
    evidence_count: int = Field(ge=1)
    self_edge: bool = False


class CitationGraphSummary(BaseModel):
    source_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    sources_with_outgoing_count: int = Field(ge=0)
    sources_with_incoming_count: int = Field(ge=0)
    url_reference_evidence_count: int = Field(ge=0)
    identifier_reference_evidence_count: int = Field(ge=0)
    unresolved_url_reference_count: int = Field(ge=0)
    ambiguous_url_reference_count: int = Field(ge=0)
    unresolved_identifier_reference_count: int = Field(ge=0)
    ambiguous_identifier_reference_count: int = Field(ge=0)
    self_edge_count: int = Field(ge=0)


class WorkspaceCitationGraph(BaseModel):
    workspace_id: str
    graph_version: str
    summary: CitationGraphSummary
    nodes: list[CitationGraphNode]
    edges: list[CitationGraphEdge]
    interpretation_note: str
