from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.analysis import AssertionPolarity, RelationEvidence


class GraphNode(BaseModel):
    entity_id: str
    label: str
    entity_type: str
    mention_count: int = Field(ge=1)
    source_count: int = Field(ge=1)
    in_degree: int = Field(ge=0)
    out_degree: int = Field(ge=0)
    degree_centrality: float = Field(ge=0.0)
    pagerank: float = Field(ge=0.0)
    betweenness: float = Field(ge=0.0)
    community: int = Field(ge=0)


class GraphEdge(BaseModel):
    relation_id: str
    source_entity_id: str
    target_entity_id: str
    predicate: str
    polarity: AssertionPolarity
    polarity_method: str
    extraction_score: float = Field(ge=0.0, le=1.0)
    extraction_method: str
    evidence_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    evidence: list[RelationEvidence] = Field(default_factory=list)


class GraphSummary(BaseModel):
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    density: float = Field(ge=0.0)
    weak_component_count: int = Field(ge=0)
    community_count: int = Field(ge=0)


class EvidenceGraph(BaseModel):
    run_id: str
    workspace_id: str
    graph_version: str
    summary: GraphSummary
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphPathStep(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relation_ids: list[str] = Field(default_factory=list)


class GraphPath(BaseModel):
    run_id: str
    source_entity_id: str
    target_entity_id: str
    directed: bool = False
    hop_count: int = Field(ge=0)
    entity_ids: list[str]
    steps: list[GraphPathStep]
