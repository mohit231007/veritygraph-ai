from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.domain.retrieval import (
    CitationContextDirection,
    RetrievalCitationContext,
    RetrievalHit,
    RetrievalPreviewSummary,
    WorkspaceRetrievalPreview,
)
from app.domain.source import SourceDocument, SourceSpan
from app.domain.workspace import WorkspaceDetail
from app.repositories.source_repository import SourceRepository
from app.services.citation_graph import build_workspace_citation_graph

RETRIEVAL_VERSION = "provenance-bm25-retrieval-v1"
INTERPRETATION_NOTE = (
    "Direct hits are ranked only from persisted SourceSpan text using deterministic local lexical "
    "BM25 scoring. Citation neighbors are returned separately as discovery context and do not "
    "change hit scores, become answer evidence, or imply support for the query. A citation-context "
    "item means only that a directly matched source has an explicit uniquely resolved citation "
    "edge to or from another workspace source. No embedding model, LLM, web search, registry "
    "lookup, or semantic reranker participates in this preview."
)
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[._/-][A-Za-z0-9]+)*")
_BM25_K1 = 1.5
_BM25_B = 0.75


@dataclass(frozen=True)
class RankedWorkspaceSpans:
    hits: list[RetrievalHit]
    indexed_span_count: int
    query_terms: list[str]


def _label(document: SourceDocument) -> str:
    return document.filename or document.title


def _tokens(value: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN_PATTERN.finditer(value)]


def _ordered_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _workspace_spans(
    workspace: WorkspaceDetail,
    *,
    source_repository: SourceRepository,
) -> list[SourceSpan]:
    spans: list[SourceSpan] = []
    for document in workspace.sources:
        bundle = source_repository.get(document.source_id)
        if bundle is not None:
            spans.extend(bundle.spans)
    return spans


def _bm25_scores(
    spans: list[SourceSpan],
    query_terms: list[str],
) -> list[tuple[SourceSpan, float, list[str]]]:
    if not spans or not query_terms:
        return []

    token_counts = [Counter(_tokens(span.text)) for span in spans]
    lengths = [sum(counts.values()) for counts in token_counts]
    average_length = sum(lengths) / len(lengths) if lengths else 0.0
    if average_length <= 0:
        return []

    document_frequency = {
        term: sum(term in counts for counts in token_counts) for term in query_terms
    }
    document_count = len(spans)
    results: list[tuple[SourceSpan, float, list[str]]] = []

    for span, counts, length in zip(spans, token_counts, lengths, strict=True):
        score = 0.0
        matched_terms: list[str] = []
        for term in query_terms:
            frequency = counts.get(term, 0)
            if frequency <= 0:
                continue
            matched_terms.append(term)
            frequency_in_documents = document_frequency[term]
            inverse_document_frequency = math.log(
                1
                + (document_count - frequency_in_documents + 0.5)
                / (frequency_in_documents + 0.5)
            )
            denominator = frequency + _BM25_K1 * (
                1 - _BM25_B + _BM25_B * length / average_length
            )
            score += inverse_document_frequency * (
                frequency * (_BM25_K1 + 1) / denominator
            )

        if score > 0:
            results.append((span, score, matched_terms))
    return results


def rank_workspace_spans(
    workspace: WorkspaceDetail,
    *,
    query: str,
    limit: int,
    source_repository: SourceRepository,
) -> RankedWorkspaceSpans:
    """Run the production lexical ranker without graph expansion."""

    documents = {document.source_id: document for document in workspace.sources}
    spans = _workspace_spans(workspace, source_repository=source_repository)
    query_terms = _ordered_unique(_tokens(query))
    scored = _bm25_scores(spans, query_terms)
    scored.sort(
        key=lambda item: (
            -item[1],
            _label(documents[item[0].source_id]).casefold(),
            item[0].char_start,
            item[0].span_id,
        )
    )
    selected = scored[: max(0, limit)]
    hits = [
        RetrievalHit(
            rank=index,
            source_id=span.source_id,
            source_label=_label(documents[span.source_id]),
            span_id=span.span_id,
            text=span.text,
            page_number=span.page_number,
            section=span.section,
            paragraph_number=span.paragraph_number,
            char_start=span.char_start,
            char_end=span.char_end,
            score=round(score, 6),
            matched_terms=matched_terms,
        )
        for index, (span, score, matched_terms) in enumerate(selected, start=1)
    ]
    return RankedWorkspaceSpans(
        hits=hits,
        indexed_span_count=len(spans),
        query_terms=query_terms,
    )


def build_workspace_retrieval_preview(
    workspace: WorkspaceDetail,
    *,
    query: str,
    limit: int,
    source_repository: SourceRepository,
) -> WorkspaceRetrievalPreview:
    """Rank persisted spans, then attach citation neighbors as non-evidence context."""

    ranked = rank_workspace_spans(
        workspace,
        query=query,
        limit=limit,
        source_repository=source_repository,
    )
    hits = ranked.hits
    hit_source_ids = {hit.source_id for hit in hits}
    citation_graph = build_workspace_citation_graph(
        workspace,
        source_repository=source_repository,
    )
    citation_context: list[RetrievalCitationContext] = []
    seen_context: set[tuple[str, str, str]] = set()

    for edge in citation_graph.edges:
        if edge.source_id in hit_source_ids:
            key = (edge.edge_id, edge.source_id, CitationContextDirection.OUTGOING.value)
            if key not in seen_context:
                seen_context.add(key)
                citation_context.append(
                    RetrievalCitationContext(
                        edge_id=edge.edge_id,
                        seed_source_id=edge.source_id,
                        seed_source_label=edge.source_label,
                        direction=CitationContextDirection.OUTGOING,
                        neighbor_source_id=edge.target_source_id,
                        neighbor_label=edge.target_label,
                        mechanisms=edge.mechanisms,
                        evidence_count=edge.evidence_count,
                    )
                )
        if edge.target_source_id in hit_source_ids and edge.target_source_id != edge.source_id:
            key = (edge.edge_id, edge.target_source_id, CitationContextDirection.INCOMING.value)
            if key not in seen_context:
                seen_context.add(key)
                citation_context.append(
                    RetrievalCitationContext(
                        edge_id=edge.edge_id,
                        seed_source_id=edge.target_source_id,
                        seed_source_label=edge.target_label,
                        direction=CitationContextDirection.INCOMING,
                        neighbor_source_id=edge.source_id,
                        neighbor_label=edge.source_label,
                        mechanisms=edge.mechanisms,
                        evidence_count=edge.evidence_count,
                    )
                )

    citation_context.sort(
        key=lambda item: (
            item.seed_source_label.casefold(),
            item.direction.value,
            item.neighbor_label.casefold(),
            item.edge_id,
        )
    )

    return WorkspaceRetrievalPreview(
        workspace_id=workspace.workspace_id,
        retrieval_version=RETRIEVAL_VERSION,
        query=query,
        summary=RetrievalPreviewSummary(
            workspace_source_count=len(workspace.sources),
            indexed_span_count=ranked.indexed_span_count,
            query_term_count=len(ranked.query_terms),
            direct_hit_count=len(hits),
            direct_hit_source_count=len(hit_source_ids),
            citation_context_count=len(citation_context),
        ),
        hits=hits,
        citation_context=citation_context,
        interpretation_note=INTERPRETATION_NOTE,
    )
