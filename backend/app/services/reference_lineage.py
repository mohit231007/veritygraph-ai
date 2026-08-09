from __future__ import annotations

from collections import defaultdict

from app.domain.lineage import (
    ReferenceLineageEdge,
    ReferenceLineageSummary,
    ReferenceResolution,
    WorkspaceReferenceLineage,
)
from app.domain.source import SourceDocument
from app.domain.workspace import WorkspaceDetail
from app.repositories.source_repository import SourceRepository
from app.services.source_references import normalize_reference_url

LINEAGE_VERSION = "explicit-reference-lineage-v2-format-links"
INTERPRETATION_NOTE = (
    "Reference lineage contains only explicit HTTP(S) targets retained during ingestion, "
    "including visible URLs and supported format-level link metadata. A page or paragraph "
    "locator identifies where the link was observed; it does not mean the target URL itself "
    "was present in extracted NLP text. A workspace resolution means the normalized target "
    "URL matches persisted URL metadata for one or more sources currently in this workspace; "
    "it does not prove quotation, endorsement, factual dependence, or direction of copying. "
    "An external target may simply not have been ingested. Multiple workspace sources with "
    "the same URL remain ambiguous rather than being collapsed arbitrarily."
)


def _label(document: SourceDocument) -> str:
    return document.filename or document.title


def _url_aliases(document: SourceDocument) -> set[str]:
    candidates: list[str] = []
    if document.url:
        candidates.append(document.url)
    for key in ("requested_url", "final_url"):
        value = document.metadata.get(key)
        if isinstance(value, str):
            candidates.append(value)

    aliases: set[str] = set()
    for candidate in candidates:
        normalized = normalize_reference_url(candidate)
        if normalized is not None:
            aliases.add(normalized)
    return aliases


def build_workspace_reference_lineage(
    workspace: WorkspaceDetail,
    *,
    source_repository: SourceRepository,
) -> WorkspaceReferenceLineage:
    """Resolve explicit source references against current workspace URL identities."""

    documents = {document.source_id: document for document in workspace.sources}
    targets_by_url: dict[str, list[SourceDocument]] = defaultdict(list)
    for document in workspace.sources:
        for alias in _url_aliases(document):
            targets_by_url[alias].append(document)

    edges: list[ReferenceLineageEdge] = []
    for source_id in [document.source_id for document in workspace.sources]:
        bundle = source_repository.get(source_id)
        if bundle is None:
            continue
        source_document = documents[source_id]
        for reference in bundle.references:
            candidates = sorted(
                targets_by_url.get(reference.normalized_target_url, []),
                key=lambda item: (item.created_at, item.source_id),
            )
            if not candidates:
                resolution = ReferenceResolution.EXTERNAL
            elif len(candidates) == 1:
                resolution = ReferenceResolution.WORKSPACE_UNIQUE
            else:
                resolution = ReferenceResolution.WORKSPACE_AMBIGUOUS

            target_source_ids = [document.source_id for document in candidates]
            target_labels = [_label(document) for document in candidates]
            self_reference = source_id in target_source_ids
            edges.append(
                ReferenceLineageEdge(
                    reference_id=reference.reference_id,
                    source_id=source_id,
                    source_label=_label(source_document),
                    span_id=reference.span_id,
                    page_number=reference.page_number,
                    paragraph_number=reference.paragraph_number,
                    target_url=reference.target_url,
                    normalized_target_url=reference.normalized_target_url,
                    resolution=resolution,
                    target_source_ids=target_source_ids,
                    target_labels=target_labels,
                    anchor_text=reference.anchor_text,
                    context_text=reference.context_text,
                    extraction_method=reference.extraction_method,
                    self_reference=self_reference,
                )
            )

    edges.sort(
        key=lambda edge: (
            edge.source_label.casefold(),
            edge.page_number or 0,
            edge.paragraph_number or 0,
            edge.normalized_target_url,
            edge.span_id or "",
            edge.reference_id,
        )
    )
    resolved_count = sum(
        edge.resolution == ReferenceResolution.WORKSPACE_UNIQUE for edge in edges
    )
    ambiguous_count = sum(
        edge.resolution == ReferenceResolution.WORKSPACE_AMBIGUOUS for edge in edges
    )
    external_count = sum(edge.resolution == ReferenceResolution.EXTERNAL for edge in edges)
    self_count = sum(edge.self_reference for edge in edges)

    return WorkspaceReferenceLineage(
        workspace_id=workspace.workspace_id,
        lineage_version=LINEAGE_VERSION,
        summary=ReferenceLineageSummary(
            source_count=len(workspace.sources),
            reference_count=len(edges),
            resolved_workspace_reference_count=resolved_count,
            ambiguous_workspace_reference_count=ambiguous_count,
            external_reference_count=external_count,
            self_reference_count=self_count,
        ),
        references=edges,
        interpretation_note=INTERPRETATION_NOTE,
    )
