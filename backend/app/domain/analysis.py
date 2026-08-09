from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AnalysisStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisRun(BaseModel):
    run_id: str
    workspace_id: str
    status: AnalysisStatus
    pipeline_version: str
    model_name: str
    model_version: str
    extractor_version: str
    resolver_version: str = "none"
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    source_count: int = Field(default=0, ge=0)
    span_count: int = Field(default=0, ge=0)
    entity_count: int = Field(default=0, ge=0)
    relation_count: int = Field(default=0, ge=0)
    error: str | None = None


class EntityMention(BaseModel):
    mention_id: str
    entity_id: str
    source_id: str
    span_id: str
    text: str
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)


class Entity(BaseModel):
    entity_id: str
    run_id: str
    canonical_name: str
    entity_type: str
    normalized_key: str
    mention_count: int = Field(ge=1)
    mentions: list[EntityMention] = Field(default_factory=list)


class RelationEvidence(BaseModel):
    evidence_id: str
    relation_id: str
    source_id: str
    span_id: str
    text: str
    sentence_start: int = Field(ge=0)
    sentence_end: int = Field(ge=0)


class Relation(BaseModel):
    relation_id: str
    run_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    extraction_score: float = Field(ge=0.0, le=1.0)
    extraction_method: str
    evidence: list[RelationEvidence] = Field(default_factory=list)


class WorkspaceAnalysis(BaseModel):
    run: AnalysisRun
    entities: list[Entity]
    relations: list[Relation]
