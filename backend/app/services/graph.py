from __future__ import annotations

from collections import defaultdict

import networkx as nx

from app.domain.analysis import (
    AssertionModality,
    AssertionPolarity,
    WorkspaceAnalysis,
)
from app.domain.graph import (
    EvidenceGraph,
    GraphEdge,
    GraphNode,
    GraphPath,
    GraphPathStep,
    GraphSummary,
)

GRAPH_VERSION = "evidence-graph-v3-qualifiers"


class GraphPathNotFoundError(ValueError):
    """Raised when two requested entities are not connected in the analysis graph."""


def _is_structural_relation(polarity: AssertionPolarity, modality: AssertionModality) -> bool:
    return polarity != AssertionPolarity.NEGATED and modality != AssertionModality.MODAL


def _analytics_projection(analysis: WorkspaceAnalysis) -> nx.DiGraph:
    graph = nx.DiGraph()
    for entity in analysis.entities:
        graph.add_node(entity.entity_id)

    for relation in analysis.relations:
        # Explicit negation and modal/future assertions remain inspectable evidence,
        # but neither is allowed to masquerade as an established graph relationship.
        if not _is_structural_relation(relation.polarity, relation.modality):
            continue
        support = max(1, len(relation.evidence))
        source_id = relation.subject_entity_id
        target_id = relation.object_entity_id
        if graph.has_edge(source_id, target_id):
            graph[source_id][target_id]["weight"] += support
        else:
            graph.add_edge(source_id, target_id, weight=support)
    return graph


def _communities(graph: nx.DiGraph) -> dict[str, int]:
    undirected = graph.to_undirected()
    if undirected.number_of_nodes() == 0:
        return {}
    if undirected.number_of_edges() == 0:
        return {node_id: index for index, node_id in enumerate(undirected.nodes())}

    communities = nx.community.greedy_modularity_communities(undirected, weight="weight")
    return {
        node_id: community_index
        for community_index, community in enumerate(communities)
        for node_id in community
    }


def build_evidence_graph(analysis: WorkspaceAnalysis) -> EvidenceGraph:
    """Project one immutable analysis run into an evidence-preserving graph view."""

    projection = _analytics_projection(analysis)
    if projection.number_of_nodes() == 0:
        pagerank: dict[str, float] = {}
    else:
        try:
            pagerank = nx.pagerank(projection, weight="weight", max_iter=200)
        except nx.PowerIterationFailedConvergence:
            uniform = 1.0 / projection.number_of_nodes()
            pagerank = {node_id: uniform for node_id in projection.nodes()}

    degree_centrality = nx.degree_centrality(projection)
    betweenness = nx.betweenness_centrality(projection, weight=None, normalized=True)
    community_by_node = _communities(projection)

    nodes = []
    for entity in analysis.entities:
        source_count = len({mention.source_id for mention in entity.mentions})
        nodes.append(
            GraphNode(
                entity_id=entity.entity_id,
                label=entity.canonical_name,
                entity_type=entity.entity_type,
                mention_count=entity.mention_count,
                source_count=max(1, source_count),
                in_degree=projection.in_degree(entity.entity_id),
                out_degree=projection.out_degree(entity.entity_id),
                degree_centrality=degree_centrality.get(entity.entity_id, 0.0),
                pagerank=pagerank.get(entity.entity_id, 0.0),
                betweenness=betweenness.get(entity.entity_id, 0.0),
                community=community_by_node.get(entity.entity_id, 0),
            )
        )
    nodes.sort(key=lambda node: (-node.pagerank, -node.betweenness, node.label.casefold()))

    edges = [
        GraphEdge(
            relation_id=relation.relation_id,
            source_entity_id=relation.subject_entity_id,
            target_entity_id=relation.object_entity_id,
            predicate=relation.predicate,
            polarity=relation.polarity,
            polarity_method=relation.polarity_method,
            modality=relation.modality,
            modality_method=relation.modality_method,
            temporal_years=relation.temporal_years,
            temporal_method=relation.temporal_method,
            extraction_score=relation.extraction_score,
            extraction_method=relation.extraction_method,
            evidence_count=len(relation.evidence),
            source_count=len({evidence.source_id for evidence in relation.evidence}),
            evidence=relation.evidence,
        )
        for relation in analysis.relations
    ]
    edges.sort(
        key=lambda edge: (
            not _is_structural_relation(edge.polarity, edge.modality),
            -edge.evidence_count,
            -edge.extraction_score,
            edge.predicate,
            tuple(edge.temporal_years),
        )
    )

    summary = GraphSummary(
        node_count=projection.number_of_nodes(),
        edge_count=len(edges),
        density=nx.density(projection),
        weak_component_count=(
            nx.number_weakly_connected_components(projection)
            if projection.number_of_nodes()
            else 0
        ),
        community_count=(max(community_by_node.values()) + 1 if community_by_node else 0),
    )
    return EvidenceGraph(
        run_id=analysis.run.run_id,
        workspace_id=analysis.run.workspace_id,
        graph_version=GRAPH_VERSION,
        summary=summary,
        nodes=nodes,
        edges=edges,
    )


def shortest_connection_path(
    analysis: WorkspaceAnalysis,
    *,
    source_entity_id: str,
    target_entity_id: str,
) -> GraphPath:
    """Return the fewest-hop undirected established/legacy connection path."""

    projection = _analytics_projection(analysis)
    if source_entity_id not in projection or target_entity_id not in projection:
        raise GraphPathNotFoundError("One or both entities are not present in this analysis run.")

    undirected = projection.to_undirected()
    try:
        entity_ids = nx.shortest_path(
            undirected,
            source=source_entity_id,
            target=target_entity_id,
        )
    except nx.NetworkXNoPath as exc:
        raise GraphPathNotFoundError("No connection path exists between these entities.") from exc

    relations_by_pair: dict[frozenset[str], list[str]] = defaultdict(list)
    for relation in analysis.relations:
        if not _is_structural_relation(relation.polarity, relation.modality):
            continue
        pair = frozenset({relation.subject_entity_id, relation.object_entity_id})
        relations_by_pair[pair].append(relation.relation_id)

    steps = [
        GraphPathStep(
            source_entity_id=left,
            target_entity_id=right,
            relation_ids=relations_by_pair[frozenset({left, right})],
        )
        for left, right in zip(entity_ids, entity_ids[1:], strict=False)
    ]
    return GraphPath(
        run_id=analysis.run.run_id,
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        directed=False,
        hop_count=max(0, len(entity_ids) - 1),
        entity_ids=entity_ids,
        steps=steps,
    )
