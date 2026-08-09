from __future__ import annotations

from collections import defaultdict

from app.domain.lineage import (
    IdentifierLineageObservation,
    IdentifierLineageSummary,
    IdentifierMatchResolution,
    WorkspaceIdentifierLineage,
)
from app.domain.source import IdentifierObservationRole, SourceDocument
from app.domain.workspace import WorkspaceDetail
from app.repositories.source_repository import SourceRepository

LINEAGE_VERSION = "bibliographic-identity-lineage-v1"
INTERPRETATION_NOTE = (
    "Bibliographic identity lineage contains only explicit DOI, arXiv, and validated ISBN "
    "observations retained during ingestion. An exact normalized identifier match does not prove "
    "citation, endorsement, authorship, factual support, dependence, copying, or truth. A "
    "reference-linked observation means the identifier was observed inside retained reference "
    "text or a supported reference URL, while an ordinary mention is not promoted to a citation. "
    "ISBN-10 observations are normalized to their valid ISBN-13 equivalent. arXiv base identifiers "
    "are matched across optional version suffixes, with the observed version retained separately. "
    "No registry or network lookup occurs here."
)


def _label(document: SourceDocument) -> str:
    return document.filename or document.title


def build_workspace_identifier_lineage(
    workspace: WorkspaceDetail,
    *,
    source_repository: SourceRepository,
) -> WorkspaceIdentifierLineage:
    """Project exact bibliographic identity matches across current workspace sources."""

    documents = {document.source_id: document for document in workspace.sources}
    bundles = {}
    sources_by_identity: dict[tuple[str, str], set[str]] = defaultdict(set)

    for document in workspace.sources:
        bundle = source_repository.get(document.source_id)
        if bundle is None:
            continue
        bundles[document.source_id] = bundle
        for identifier in bundle.identifiers:
            sources_by_identity[(identifier.kind.value, identifier.normalized_value)].add(
                document.source_id
            )

    observations: list[IdentifierLineageObservation] = []
    for document in workspace.sources:
        bundle = bundles.get(document.source_id)
        if bundle is None:
            continue
        for identifier in bundle.identifiers:
            candidate_ids = sorted(
                source_id
                for source_id in sources_by_identity[
                    (identifier.kind.value, identifier.normalized_value)
                ]
                if source_id != document.source_id
            )
            if not candidate_ids:
                resolution = IdentifierMatchResolution.NO_WORKSPACE_MATCH
            elif len(candidate_ids) == 1:
                resolution = IdentifierMatchResolution.WORKSPACE_UNIQUE
            else:
                resolution = IdentifierMatchResolution.WORKSPACE_AMBIGUOUS

            observations.append(
                IdentifierLineageObservation(
                    identifier_id=identifier.identifier_id,
                    source_id=document.source_id,
                    source_label=_label(document),
                    kind=identifier.kind,
                    raw_value=identifier.raw_value,
                    normalized_value=identifier.normalized_value,
                    role=identifier.role,
                    version=identifier.version,
                    span_id=identifier.span_id,
                    reference_id=identifier.reference_id,
                    page_number=identifier.page_number,
                    paragraph_number=identifier.paragraph_number,
                    resolution=resolution,
                    matching_source_ids=candidate_ids,
                    matching_labels=[_label(documents[source_id]) for source_id in candidate_ids],
                    context_text=identifier.context_text,
                    extraction_method=identifier.extraction_method,
                )
            )

    observations.sort(
        key=lambda item: (
            item.source_label.casefold(),
            item.kind.value,
            item.normalized_value,
            item.role.value,
            item.version or 0,
            item.identifier_id,
        )
    )
    unique_identifier_count = len(
        {(item.kind.value, item.normalized_value) for item in observations}
    )
    matched_count = sum(
        item.resolution != IdentifierMatchResolution.NO_WORKSPACE_MATCH
        for item in observations
    )
    ambiguous_count = sum(
        item.resolution == IdentifierMatchResolution.WORKSPACE_AMBIGUOUS
        for item in observations
    )
    reference_count = sum(
        item.role == IdentifierObservationRole.REFERENCE for item in observations
    )

    return WorkspaceIdentifierLineage(
        workspace_id=workspace.workspace_id,
        lineage_version=LINEAGE_VERSION,
        summary=IdentifierLineageSummary(
            source_count=len(workspace.sources),
            observation_count=len(observations),
            unique_identifier_count=unique_identifier_count,
            matched_observation_count=matched_count,
            ambiguous_observation_count=ambiguous_count,
            reference_linked_observation_count=reference_count,
        ),
        identifiers=observations,
        interpretation_note=INTERPRETATION_NOTE,
    )
