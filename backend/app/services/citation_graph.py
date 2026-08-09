from __future__ import annotations

from collections import defaultdict
from hashlib import sha256

from app.domain.citations import (
    CitationGraphEdge,
    CitationGraphNode,
    CitationGraphSummary,
    CitationMechanism,
    WorkspaceCitationGraph,
)
from app.domain.lineage import IdentifierMatchResolution, ReferenceResolution
from app.domain.source import IdentifierObservationRole, SourceDocument
from app.domain.workspace import WorkspaceDetail
from app.repositories.source_repository import SourceRepository
from app.services.identifier_lineage import build_workspace_identifier_lineage
from app.services.reference_lineage import build_workspace_reference_lineage

GRAPH_VERSION = "explicit-citation-graph-v1"
INTERPRETATION_NOTE = (
    "This graph contains only explicit, uniquely resolved provenance edges. A URL edge requires "
    "a retained HTTP(S) reference that resolves to exactly one workspace source. A bibliographic "
    "edge requires a reference-linked DOI, arXiv, or ISBN observation that resolves to exactly one "
    "other source explicitly attested as that identifier's source identity. Shared identifier "
    "mentions never create citation edges. Ambiguous and unresolved evidence remains counted but "
    "is excluded from topology. An edge records an explicit reference relationship; it does not "
    "prove endorsement, agreement, factual support, dependence, copying, authority, or truth."
)


def _label(document: SourceDocument) -> str:
    return document.filename or document.title


def _edge_id(source_id: str, target_source_id: str) -> str:
    material = f"{source_id}|{target_source_id}"
    return f"cite_{sha256(material.encode('utf-8')).hexdigest()[:24]}"


def build_workspace_citation_graph(
    workspace: WorkspaceDetail,
    *,
    source_repository: SourceRepository,
) -> WorkspaceCitationGraph:
    """Build deterministic source-to-source edges from already-resolved provenance."""

    documents = {document.source_id: document for document in workspace.sources}
    reference_lineage = build_workspace_reference_lineage(
        workspace,
        source_repository=source_repository,
    )
    identifier_lineage = build_workspace_identifier_lineage(
        workspace,
        source_repository=source_repository,
    )

    edge_data: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(
        lambda: {
            "mechanisms": set(),
            "url_reference_ids": set(),
            "identifier_ids": set(),
            "bibliographic_identities": set(),
        }
    )

    unresolved_url_count = 0
    ambiguous_url_count = 0
    for reference in reference_lineage.references:
        if reference.resolution == ReferenceResolution.WORKSPACE_UNIQUE:
            if len(reference.target_source_ids) != 1:
                continue
            target_source_id = reference.target_source_ids[0]
            data = edge_data[(reference.source_id, target_source_id)]
            data["mechanisms"].add(CitationMechanism.URL_REFERENCE.value)
            data["url_reference_ids"].add(reference.reference_id)
        elif reference.resolution == ReferenceResolution.WORKSPACE_AMBIGUOUS:
            ambiguous_url_count += 1
        else:
            unresolved_url_count += 1

    unresolved_identifier_count = 0
    ambiguous_identifier_count = 0
    for observation in identifier_lineage.identifiers:
        if observation.role != IdentifierObservationRole.REFERENCE:
            continue
        if observation.identity_target_resolution == IdentifierMatchResolution.WORKSPACE_UNIQUE:
            if len(observation.identity_target_source_ids) != 1:
                continue
            target_source_id = observation.identity_target_source_ids[0]
            data = edge_data[(observation.source_id, target_source_id)]
            data["mechanisms"].add(CitationMechanism.BIBLIOGRAPHIC_IDENTIFIER.value)
            data["identifier_ids"].add(observation.identifier_id)
            data["bibliographic_identities"].add(
                f"{observation.kind.value}:{observation.normalized_value}"
            )
        elif (
            observation.identity_target_resolution
            == IdentifierMatchResolution.WORKSPACE_AMBIGUOUS
        ):
            ambiguous_identifier_count += 1
        else:
            unresolved_identifier_count += 1

    edges: list[CitationGraphEdge] = []
    incoming: dict[str, int] = defaultdict(int)
    outgoing: dict[str, int] = defaultdict(int)
    url_evidence_count = 0
    identifier_evidence_count = 0

    for (source_id, target_source_id), data in sorted(edge_data.items()):
        source = documents.get(source_id)
        target = documents.get(target_source_id)
        if source is None or target is None:
            continue
        url_reference_ids = sorted(data["url_reference_ids"])
        identifier_ids = sorted(data["identifier_ids"])
        url_evidence_count += len(url_reference_ids)
        identifier_evidence_count += len(identifier_ids)
        outgoing[source_id] += 1
        incoming[target_source_id] += 1
        edges.append(
            CitationGraphEdge(
                edge_id=_edge_id(source_id, target_source_id),
                source_id=source_id,
                source_label=_label(source),
                target_source_id=target_source_id,
                target_label=_label(target),
                mechanisms=[
                    CitationMechanism(value) for value in sorted(data["mechanisms"])
                ],
                url_reference_ids=url_reference_ids,
                identifier_ids=identifier_ids,
                bibliographic_identities=sorted(data["bibliographic_identities"]),
                evidence_count=len(url_reference_ids) + len(identifier_ids),
                self_edge=source_id == target_source_id,
            )
        )

    nodes = [
        CitationGraphNode(
            source_id=document.source_id,
            label=_label(document),
            source_type=document.source_type,
            incoming_edge_count=incoming[document.source_id],
            outgoing_edge_count=outgoing[document.source_id],
        )
        for document in sorted(
            workspace.sources,
            key=lambda item: (_label(item).casefold(), item.source_id),
        )
    ]

    return WorkspaceCitationGraph(
        workspace_id=workspace.workspace_id,
        graph_version=GRAPH_VERSION,
        summary=CitationGraphSummary(
            source_count=len(workspace.sources),
            edge_count=len(edges),
            sources_with_outgoing_count=sum(node.outgoing_edge_count > 0 for node in nodes),
            sources_with_incoming_count=sum(node.incoming_edge_count > 0 for node in nodes),
            url_reference_evidence_count=url_evidence_count,
            identifier_reference_evidence_count=identifier_evidence_count,
            unresolved_url_reference_count=unresolved_url_count,
            ambiguous_url_reference_count=ambiguous_url_count,
            unresolved_identifier_reference_count=unresolved_identifier_count,
            ambiguous_identifier_reference_count=ambiguous_identifier_count,
            self_edge_count=sum(edge.self_edge for edge in edges),
        ),
        nodes=nodes,
        edges=edges,
        interpretation_note=INTERPRETATION_NOTE,
    )
