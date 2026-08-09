from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.analysis import RelationEvidence
from app.domain.source import SourceType


class ClaimSupportLevel(StrEnum):
    SINGLE_SOURCE = "single_source"
    CROSS_SOURCE = "cross_source"


class ComparisonClaim(BaseModel):
    relation_id: str
    subject_entity_id: str
    subject_label: str
    predicate: str
    object_entity_id: str
    object_label: str
    extraction_score: float = Field(ge=0.0, le=1.0)
    support_level: ClaimSupportLevel
    source_count: int = Field(ge=1)
    source_ids: list[str]
    evidence_count: int = Field(ge=1)
    evidence: list[RelationEvidence]


class SourceClaimProfile(BaseModel):
    source_id: str
    label: str
    source_type: SourceType
    claim_count: int = Field(ge=0)
    cross_source_claim_count: int = Field(ge=0)
    single_source_claim_count: int = Field(ge=0)


class SourcePairOverlap(BaseModel):
    left_source_id: str
    right_source_id: str
    shared_claim_count: int = Field(ge=0)
    union_claim_count: int = Field(ge=0)
    jaccard_similarity: float = Field(ge=0.0, le=1.0)
    shared_relation_ids: list[str]


class SourceComparisonSummary(BaseModel):
    source_count: int = Field(ge=0)
    claim_count: int = Field(ge=0)
    cross_source_claim_count: int = Field(ge=0)
    single_source_claim_count: int = Field(ge=0)
    pair_count: int = Field(ge=0)


class SourceComparison(BaseModel):
    run_id: str
    workspace_id: str
    comparison_version: str
    summary: SourceComparisonSummary
    sources: list[SourceClaimProfile]
    claims: list[ComparisonClaim]
    overlaps: list[SourcePairOverlap]
    interpretation_note: str
