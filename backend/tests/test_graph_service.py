from datetime import UTC, datetime

import pytest
from app.domain.analysis import (
    AnalysisRun,
    AnalysisStatus,
    AssertionModality,
    AssertionPolarity,
    Entity,
    EntityMention,
    Relation,
    RelationEvidence,
    WorkspaceAnalysis,
)
from app.services.graph import (
    GraphPathNotFoundError,
    build_evidence_graph,
    shortest_connection_path,
)


def mention(entity_id: str, source_id: str, index: int) -> EntityMention:
    return EntityMention(
        mention_id=f"men_{entity_id}_{index}",
        entity_id=entity_id,
        source_id=source_id,
        span_id=f"span_{source_id}",
        text=entity_id,
        start_char=0,
        end_char=len(entity_id),
    )


def entity(entity_id: str, label: str, sources: list[str]) -> Entity:
    mentions = [mention(entity_id, source_id, index) for index, source_id in enumerate(sources)]
    return Entity(
        entity_id=entity_id,
        run_id="run_graph",
        canonical_name=label,
        entity_type="ORG",
        normalized_key=f"ORG:{label.casefold()}",
        mention_count=len(mentions),
        mentions=mentions,
    )


def relation(
    relation_id: str,
    source: str,
    target: str,
    predicate: str,
    evidence_sources: list[str],
    *,
    polarity: AssertionPolarity = AssertionPolarity.AFFIRMED,
    modality: AssertionModality = AssertionModality.ASSERTED,
    years: list[int] | None = None,
) -> Relation:
    evidence = [
        RelationEvidence(
            evidence_id=f"ev_{relation_id}_{index}",
            relation_id=relation_id,
            source_id=source_id,
            span_id=f"span_{source_id}",
            text=f"Evidence for {source} {predicate} {target}.",
            sentence_start=0,
            sentence_end=32,
        )
        for index, source_id in enumerate(evidence_sources)
    ]
    return Relation(
        relation_id=relation_id,
        run_id="run_graph",
        subject_entity_id=source,
        predicate=predicate,
        object_entity_id=target,
        polarity=polarity,
        polarity_method=(
            "dependency_root_negation_v1"
            if polarity == AssertionPolarity.NEGATED
            else "dependency_no_root_negation_v1"
        ),
        modality=modality,
        modality_method=(
            "dependency_modal_auxiliary_v1"
            if modality == AssertionModality.MODAL
            else "dependency_no_modal_auxiliary_v1"
        ),
        temporal_years=years or [],
        temporal_method="sentence_year_regex_v1",
        extraction_score=0.92,
        extraction_method="dependency_subject_object",
        evidence=evidence,
    )


def analysis_fixture() -> WorkspaceAnalysis:
    return WorkspaceAnalysis(
        run=AnalysisRun(
            run_id="run_graph",
            workspace_id="ws_graph",
            status=AnalysisStatus.COMPLETED,
            pipeline_version="spacy-baseline-v1",
            model_name="en_core_web_sm",
            model_version="3.8.0",
            extractor_version="dependency-relations-v3-qualifiers",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            source_count=3,
            span_count=3,
            entity_count=4,
            relation_count=3,
        ),
        entities=[
            entity("ent_a", "Alpha", ["src_1"]),
            entity("ent_b", "Bridge", ["src_1", "src_2"]),
            entity("ent_c", "Charlie", ["src_2"]),
            entity("ent_d", "Delta", ["src_3"]),
        ],
        relations=[
            relation("rel_ab", "ent_a", "ent_b", "partner", ["src_1", "src_2"]),
            relation("rel_bc", "ent_b", "ent_c", "acquire", ["src_2"]),
            relation("rel_db", "ent_d", "ent_b", "invest in", ["src_3"]),
        ],
    )


def test_graph_projection_preserves_qualified_edges_and_computes_analytics() -> None:
    graph = build_evidence_graph(analysis_fixture())

    assert graph.graph_version == "evidence-graph-v3-qualifiers"
    assert graph.summary.node_count == 4
    assert graph.summary.edge_count == 3
    assert graph.summary.weak_component_count == 1

    bridge = next(node for node in graph.nodes if node.entity_id == "ent_b")
    assert bridge.in_degree == 2
    assert bridge.out_degree == 1

    edge = next(item for item in graph.edges if item.relation_id == "rel_ab")
    assert edge.polarity == AssertionPolarity.AFFIRMED
    assert edge.modality == AssertionModality.ASSERTED
    assert edge.temporal_years == []
    assert edge.evidence_count == 2


def test_shortest_connection_path_is_undirected_and_relation_linked() -> None:
    path = shortest_connection_path(
        analysis_fixture(), source_entity_id="ent_a", target_entity_id="ent_c"
    )
    assert path.hop_count == 2
    assert path.entity_ids == ["ent_a", "ent_b", "ent_c"]


def test_negated_edge_is_retained_but_excluded_from_established_graph_path() -> None:
    analysis = analysis_fixture()
    analysis.relations = [
        relation(
            "rel_negated",
            "ent_a",
            "ent_c",
            "acquire",
            ["src_1"],
            polarity=AssertionPolarity.NEGATED,
        )
    ]
    graph = build_evidence_graph(analysis)
    assert graph.edges[0].polarity == AssertionPolarity.NEGATED
    assert graph.summary.density == 0.0
    with pytest.raises(GraphPathNotFoundError):
        shortest_connection_path(analysis, source_entity_id="ent_a", target_entity_id="ent_c")


def test_modal_edge_is_retained_but_excluded_from_established_graph_path() -> None:
    analysis = analysis_fixture()
    analysis.relations = [
        relation(
            "rel_modal",
            "ent_a",
            "ent_c",
            "acquire",
            ["src_1"],
            modality=AssertionModality.MODAL,
            years=[2027],
        )
    ]
    graph = build_evidence_graph(analysis)
    assert graph.edges[0].modality == AssertionModality.MODAL
    assert graph.edges[0].temporal_years == [2027]
    assert graph.summary.density == 0.0
    with pytest.raises(GraphPathNotFoundError):
        shortest_connection_path(analysis, source_entity_id="ent_a", target_entity_id="ent_c")
