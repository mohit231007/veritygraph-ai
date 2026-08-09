from __future__ import annotations

from collections import Counter

from app.domain.evidence_pack import (
    EvidenceExcerpt,
    EvidencePackSummary,
    GroundedEvidencePack,
)
from app.domain.workspace import WorkspaceDetail
from app.repositories.source_repository import SourceRepository
from app.services.retrieval import RETRIEVAL_VERSION, build_workspace_retrieval_preview

EVIDENCE_PACK_VERSION = "grounded-evidence-pack-v1"
INTERPRETATION_NOTE = (
    "This pack contains only excerpts from SourceSpan records that matched the production lexical "
    "retriever. Excerpts remain tied to the original span and exact normalized-corpus character "
    "range. Citation neighbors are metadata-only discovery context: their text is not added to the "
    "pack unless one of their own spans independently matched the query. Retrieval rank and BM25 "
    "score are ranking signals, not confidence, factual correctness, source authority, or truth. "
    "No LLM or embedding model participates in evidence-pack assembly."
)


def _excerpt_window(
    text: str,
    *,
    matched_terms: list[str],
    max_chars: int,
) -> tuple[int, int, str]:
    if len(text) <= max_chars:
        return 0, len(text), text

    lowered = text.casefold()
    positions = [
        lowered.find(term.casefold())
        for term in matched_terms
        if term and lowered.find(term.casefold()) >= 0
    ]
    anchor = min(positions) if positions else 0
    start = max(0, anchor - max_chars // 3)
    end = min(len(text), start + max_chars)
    if end - start < max_chars and start > 0:
        start = max(0, end - max_chars)
    return start, end, text[start:end]


def build_grounded_evidence_pack(
    workspace: WorkspaceDetail,
    *,
    query: str,
    max_excerpts: int,
    max_excerpts_per_source: int,
    max_chars_per_excerpt: int,
    max_total_chars: int,
    source_repository: SourceRepository,
) -> GroundedEvidencePack:
    """Build a deterministic, budgeted context packet from directly retrieved spans only."""

    candidate_limit = min(100, max(max_excerpts * 5, max_excerpts))
    preview = build_workspace_retrieval_preview(
        workspace,
        query=query,
        limit=candidate_limit,
        source_repository=source_repository,
    )

    source_counts: Counter[str] = Counter()
    excerpts: list[EvidenceExcerpt] = []
    selected_chars = 0
    skipped_by_source_cap = 0
    skipped_by_budget = 0

    for hit in preview.hits:
        if len(excerpts) >= max_excerpts:
            skipped_by_budget += 1
            continue
        if source_counts[hit.source_id] >= max_excerpts_per_source:
            skipped_by_source_cap += 1
            continue

        remaining_chars = max_total_chars - selected_chars
        if remaining_chars <= 0:
            skipped_by_budget += 1
            continue

        excerpt_budget = min(max_chars_per_excerpt, remaining_chars)
        relative_start, relative_end, text = _excerpt_window(
            hit.text,
            matched_terms=hit.matched_terms,
            max_chars=excerpt_budget,
        )
        if not text:
            skipped_by_budget += 1
            continue

        excerpts.append(
            EvidenceExcerpt(
                rank=hit.rank,
                source_id=hit.source_id,
                source_label=hit.source_label,
                span_id=hit.span_id,
                page_number=hit.page_number,
                section=hit.section,
                paragraph_number=hit.paragraph_number,
                span_char_start=hit.char_start,
                span_char_end=hit.char_end,
                excerpt_char_start=hit.char_start + relative_start,
                excerpt_char_end=hit.char_start + relative_end,
                text=text,
                score=hit.score,
                matched_terms=hit.matched_terms,
                truncated_before=relative_start > 0,
                truncated_after=relative_end < len(hit.text),
            )
        )
        source_counts[hit.source_id] += 1
        selected_chars += len(text)

    selected_source_ids = {excerpt.source_id for excerpt in excerpts}
    citation_context = [
        item
        for item in preview.citation_context
        if item.seed_source_id in selected_source_ids
    ]

    return GroundedEvidencePack(
        workspace_id=workspace.workspace_id,
        pack_version=EVIDENCE_PACK_VERSION,
        retrieval_version=RETRIEVAL_VERSION,
        query=query,
        summary=EvidencePackSummary(
            workspace_source_count=preview.summary.workspace_source_count,
            indexed_span_count=preview.summary.indexed_span_count,
            candidate_hit_count=len(preview.hits),
            selected_excerpt_count=len(excerpts),
            selected_source_count=len(selected_source_ids),
            selected_char_count=selected_chars,
            skipped_by_source_cap=skipped_by_source_cap,
            skipped_by_budget=skipped_by_budget,
            citation_context_count=len(citation_context),
        ),
        excerpts=excerpts,
        citation_context=citation_context,
        interpretation_note=INTERPRETATION_NOTE,
    )
