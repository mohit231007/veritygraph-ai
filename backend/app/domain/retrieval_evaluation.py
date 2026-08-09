from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RetrievalEvaluationCase(BaseModel):
    case_id: str
    query: str = Field(min_length=2, max_length=500)
    relevant_span_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("case_id", "query")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if not normalized:
            raise ValueError("value must contain non-whitespace characters")
        return normalized

    @field_validator("relevant_span_ids")
    @classmethod
    def normalize_span_ids(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized:
                raise ValueError("relevant span ids must not be blank")
            if normalized not in seen:
                cleaned.append(normalized)
                seen.add(normalized)
        return cleaned


class RetrievalEvaluationRequest(BaseModel):
    cases: list[RetrievalEvaluationCase] = Field(min_length=1, max_length=100)
    k_values: list[int] = Field(default_factory=lambda: [1, 3, 5])

    @field_validator("k_values")
    @classmethod
    def validate_k_values(cls, values: list[int]) -> list[int]:
        if not values:
            raise ValueError("at least one k value is required")
        normalized = sorted(set(values))
        if normalized[0] < 1 or normalized[-1] > 25:
            raise ValueError("k values must be between 1 and 25")
        return normalized


class RetrievalCaseMetricAtK(BaseModel):
    k: int = Field(ge=1)
    recall: float = Field(ge=0, le=1)
    precision: float = Field(ge=0, le=1)
    hit: bool


class RetrievalAggregateMetricAtK(BaseModel):
    k: int = Field(ge=1)
    mean_recall: float = Field(ge=0, le=1)
    mean_precision: float = Field(ge=0, le=1)
    hit_rate: float = Field(ge=0, le=1)


class RetrievalEvaluationCaseResult(BaseModel):
    case_id: str
    query: str
    relevant_span_ids: list[str]
    retrieved_span_ids: list[str]
    first_relevant_rank: int | None = Field(default=None, ge=1)
    reciprocal_rank: float = Field(ge=0, le=1)
    metrics_at_k: list[RetrievalCaseMetricAtK]


class RetrievalEvaluationSummary(BaseModel):
    workspace_source_count: int = Field(ge=0)
    indexed_span_count: int = Field(ge=0)
    case_count: int = Field(ge=0)
    unique_relevant_span_count: int = Field(ge=0)
    mean_reciprocal_rank: float = Field(ge=0, le=1)
    metrics_at_k: list[RetrievalAggregateMetricAtK]


class WorkspaceRetrievalEvaluation(BaseModel):
    workspace_id: str
    evaluation_version: str
    retrieval_version: str
    summary: RetrievalEvaluationSummary
    cases: list[RetrievalEvaluationCaseResult]
    interpretation_note: str
