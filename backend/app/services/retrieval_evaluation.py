from __future__ import annotations

from collections import defaultdict

from app.domain.retrieval_evaluation import (
    RetrievalAggregateMetricAtK,
    RetrievalCaseMetricAtK,
    RetrievalEvaluationCase,
    RetrievalEvaluationCaseResult,
    RetrievalEvaluationSummary,
    WorkspaceRetrievalEvaluation,
)
from app.domain.workspace import WorkspaceDetail
from app.repositories.source_repository import SourceRepository
from app.services.retrieval import RETRIEVAL_VERSION, rank_workspace_spans

EVALUATION_VERSION = "retrieval-evaluation-v1"
INTERPRETATION_NOTE = (
    "Metrics compare the production lexical ranker against explicit relevant SourceSpan labels. "
    "Recall@K measures the fraction of labelled relevant spans present in the first K ranks. "
    "Precision@K uses K as the denominator, and hit rate records whether at least one labelled "
    "relevant span appears by K. Mean reciprocal rank uses the first relevant rank across the full "
    "lexically matched ranking; a case with no retrieved relevant span contributes zero. These "
    "metrics evaluate retrieval against the supplied labels only and do not measure factual "
    "correctness, source authority, answer quality, or truth. Citation context is not part of the "
    "ranked list or evaluation score."
)


class RetrievalEvaluationError(ValueError):
    """Raised when an evaluation label does not match the current workspace."""


def _workspace_span_ids(
    workspace: WorkspaceDetail,
    *,
    source_repository: SourceRepository,
) -> set[str]:
    span_ids: set[str] = set()
    for document in workspace.sources:
        bundle = source_repository.get(document.source_id)
        if bundle is not None:
            span_ids.update(span.span_id for span in bundle.spans)
    return span_ids


def _validate_cases(
    cases: list[RetrievalEvaluationCase],
    *,
    workspace_span_ids: set[str],
) -> None:
    case_ids: set[str] = set()
    problems: list[str] = []
    for case in cases:
        if case.case_id in case_ids:
            problems.append(f"duplicate case_id {case.case_id!r}")
        case_ids.add(case.case_id)
        missing = [
            span_id for span_id in case.relevant_span_ids if span_id not in workspace_span_ids
        ]
        if missing:
            preview = ", ".join(missing[:5])
            suffix = " …" if len(missing) > 5 else ""
            problems.append(f"{case.case_id}: unknown relevant span id(s): {preview}{suffix}")
    if problems:
        raise RetrievalEvaluationError("; ".join(problems))


def _metric_at_k(
    ranked_span_ids: list[str],
    relevant_span_ids: set[str],
    k: int,
) -> RetrievalCaseMetricAtK:
    top_k = ranked_span_ids[:k]
    relevant_retrieved = len(relevant_span_ids.intersection(top_k))
    return RetrievalCaseMetricAtK(
        k=k,
        recall=round(relevant_retrieved / len(relevant_span_ids), 6),
        precision=round(relevant_retrieved / k, 6),
        hit=relevant_retrieved > 0,
    )


def evaluate_workspace_retrieval(
    workspace: WorkspaceDetail,
    *,
    cases: list[RetrievalEvaluationCase],
    k_values: list[int],
    source_repository: SourceRepository,
) -> WorkspaceRetrievalEvaluation:
    """Evaluate the exact production ranker against explicit span-level gold labels."""

    workspace_span_ids = _workspace_span_ids(
        workspace,
        source_repository=source_repository,
    )
    _validate_cases(cases, workspace_span_ids=workspace_span_ids)

    maximum_k = max(k_values)
    ranking_limit = max(1, len(workspace_span_ids))
    case_results: list[RetrievalEvaluationCaseResult] = []
    aggregate_recall: dict[int, list[float]] = defaultdict(list)
    aggregate_precision: dict[int, list[float]] = defaultdict(list)
    aggregate_hits: dict[int, list[float]] = defaultdict(list)
    reciprocal_ranks: list[float] = []

    for case in cases:
        ranked = rank_workspace_spans(
            workspace,
            query=case.query,
            limit=ranking_limit,
            source_repository=source_repository,
        )
        ranked_span_ids = [hit.span_id for hit in ranked.hits]
        relevant = set(case.relevant_span_ids)
        first_relevant_rank = next(
            (
                index
                for index, span_id in enumerate(ranked_span_ids, start=1)
                if span_id in relevant
            ),
            None,
        )
        reciprocal_rank = (
            round(1 / first_relevant_rank, 6) if first_relevant_rank is not None else 0.0
        )
        reciprocal_ranks.append(reciprocal_rank)

        metrics = [
            _metric_at_k(ranked_span_ids, relevant, k)
            for k in k_values
        ]
        for metric in metrics:
            aggregate_recall[metric.k].append(metric.recall)
            aggregate_precision[metric.k].append(metric.precision)
            aggregate_hits[metric.k].append(1.0 if metric.hit else 0.0)

        case_results.append(
            RetrievalEvaluationCaseResult(
                case_id=case.case_id,
                query=case.query,
                relevant_span_ids=case.relevant_span_ids,
                retrieved_span_ids=ranked_span_ids[:maximum_k],
                first_relevant_rank=first_relevant_rank,
                reciprocal_rank=reciprocal_rank,
                metrics_at_k=metrics,
            )
        )

    aggregate_metrics = [
        RetrievalAggregateMetricAtK(
            k=k,
            mean_recall=round(sum(aggregate_recall[k]) / len(cases), 6),
            mean_precision=round(sum(aggregate_precision[k]) / len(cases), 6),
            hit_rate=round(sum(aggregate_hits[k]) / len(cases), 6),
        )
        for k in k_values
    ]
    unique_relevant_span_ids = {
        span_id for case in cases for span_id in case.relevant_span_ids
    }

    return WorkspaceRetrievalEvaluation(
        workspace_id=workspace.workspace_id,
        evaluation_version=EVALUATION_VERSION,
        retrieval_version=RETRIEVAL_VERSION,
        summary=RetrievalEvaluationSummary(
            workspace_source_count=len(workspace.sources),
            indexed_span_count=len(workspace_span_ids),
            case_count=len(cases),
            unique_relevant_span_count=len(unique_relevant_span_ids),
            mean_reciprocal_rank=round(sum(reciprocal_ranks) / len(cases), 6),
            metrics_at_k=aggregate_metrics,
        ),
        cases=case_results,
        interpretation_note=INTERPRETATION_NOTE,
    )
