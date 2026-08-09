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

LINEAGE_VERSION = "bibliographic-identity-lineage-v2-source-attestation"
INTERPRETATION_NOTE = (
    "Bibliographic lineage contains explicit DOI, arXiv, and validated ISBN observations. "
    "A shared identifier observation only means multiple sources retained the same normalized "
    "identifier; it does not prove those sources are the identified work. Source identity is "
    "narrower and is attested only when the source acquisition URL itself is a supported DOI "
    "resolver or arXiv work URL. Source identity does not prove citation, endorsement, authorship, "
    "factual support, dependence, copying, or truth. Reference-linked observations remain distinct "
    "from ordinary mentions. ISBN-10 observations normalize to the valid ISBN-13 equivalent, and "
    "arXiv base identifiers match across optional version suffixes while retaining the observed "
    "version separately. No registry or network lookup occurs during this projection."
)


def _label(document: SourceDocument) -> str:
    return document.filename or document.title


def _resolution(candidate_ids: list[str]) -> IdentifierMatchResolution:
    if not candidate_ids:
        return IdentifierMatchResolution.NO_WORKSPACE_MATCH
    if len(candidate_ids) == 1:
        return IdentifierMatchResolution.WORKSPACE_UNIQUE
    return IdentifierMatchResolution.WORKSPACE_AMBIGUOUS


def build_workspace_identifier_lineage(
    workspace: WorkspaceDetail,
    *,
    source_repository: SourceRepository,
) -> WorkspaceIdentifierLineage:
    """Project shared observations and explicit source-identity attestations separately."""

    documents = {document.source_id: document for document in workspace.sources}
    bundles = {}
    sources_by_observation: dict[tuple[str, str], set[str]] = defaultdict(set)
    identity_sources_by_identifier: dict[tuple[str, str], set[str]] = defaultdict(set)

    for document in workspace.sources:
        bundle = source_repository.get(document.source_id)
        if bundle is None:
            continue
        bundles[document.source_id] = bundle
        for identifier in bundle.identifiers:
            identity_key = (identifier.kind.value, identifier.normalized_value)
            sources_by_observation[identity_key].add(document.source_id)
            if identifier.role == IdentifierObservationRole.SOURCE_IDENTITY:
                identity_sources_by_identifier[identity_key].add(document.source_id)

    observations: list[IdentifierLineageObservation] = []
    for document in workspace.sources:
        bundle = bundles.get(document.source_id)
        if bundle is None:
            continue
        for identifier in bundle.identifiers:
            identity_key = (identifier.kind.value, identifier.normalized_value)
            shared_candidate_ids = sorted(
                source_id
                for source_id in sources_by_observation[identity_key]
                if source_id != document.source_id
            )
            identity_target_ids = sorted(
                source_id
                for source_id in identity_sources_by_identifier[identity_key]
                if source_id != document.source_id
            )

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
                    resolution=_resolution(shared_candidate_ids),
                    matching_source_ids=shared_candidate_ids,
                    matching_labels=[
                        _label(documents[source_id]) for source_id in shared_candidate_ids
                    ],
                    identity_target_resolution=_resolution(identity_target_ids),
                    identity_target_source_ids=identity_target_ids,
                    identity_target_labels=[
                        _label(documents[source_id]) for source_id in identity_target_ids
                    ],
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
    source_identity_count = sum(
        item.role == IdentifierObservationRole.SOURCE_IDENTITY for item in observations
    )
    resolved_identity_count = sum(
        item.identity_target_resolution == IdentifierMatchResolution.WORKSPACE_UNIQUE
        for item in observations
    )
    ambiguous_identity_count = sum(
        item.identity_target_resolution == IdentifierMatchResolution.WORKSPACE_AMBIGUOUS
        for item in observations
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
            source_identity_observation_count=source_identity_count,
            resolved_identity_target_observation_count=resolved_identity_count,
            ambiguous_identity_target_observation_count=ambiguous_identity_count,
        ),
        identifiers=observations,
        interpretation_note=INTERPRETATION_NOTE,
    )
