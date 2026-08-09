from datetime import UTC, datetime

from app.domain.analysis import (
    AnalysisRun,
    AnalysisStatus,
    Entity,
    EntityMention,
    Relation,
    RelationEvidence,
    WorkspaceAnalysis,
)
from app.domain.comparison import ClaimSupportLevel
from app.domain.source import SourceDocument, SourceType
from app.services.comparison import build_source_comparison


def source(source_id: str, filename: str) -> SourceDocument:
    return SourceDocument(
        source_id=source_id,
        source_type=SourceType.DOCUMENT,
        title=filename,
        filename=filename,
        source_format="txt",
        mime_type="text/plain",
        content_hash=source_id[-1] * 64,
        size_bytes=10,
        metadata={},
    )


def entity(entity_id: str, label: str, source_ids: list[str]) -> Entity:
    mentions = [
        EntityMention(
            mention_id=f"men_{entity_id}_{index}",
            entity_id=entity_id,
            source_id=source_id,
            span_id=f"span_{source_id}",
            text=label,
            start_char=0,
            end_char=len(label),
        )
        for index, source_id in enumerate(source_ids)
    ]
    return Entity(
        entity_id=entity_id,
        run_id="run_compare",
        canonical_name=label,
        entity_type="ORG",
        normalized_key=f"ORG:{label.casefold()}",
        mention_count=len(mentions),
        mentions=mentions,
    )


def relation(
    relation_id: str,
    subject: str,
    target: str,
    source_ids: list[str],
) -> Relation:
    evidence = [
        RelationEvidence(
            evidence_id=f"ev_{relation_id}_{index}",
            relation_id=relation_id,
            source_id=source_id,
            span_id=f"span_{source_id}",
            text=f"Evidence from {source_id}.",
            sentence_start=0,
            sentence_end=20,
        )
        for index, source_id in enumerate(source_ids)
    ]
    return Relation(
        relation_id=relation_id,
        run_id="run_compare",
        subject_entity_id=subject,
        predicate="acquire",
        object_entity_id=target,
        extraction_score=0.92,
        extraction_method="dependency_subject_object",
        evidence=evidence,
    )


def analysis_fixture() -> WorkspaceAnalysis:
    return WorkspaceAnalysis(
        run=AnalysisRun(
            run_id="run_compare",
            workspace_id="ws_compare",
            status=AnalysisStatus.COMPLETED,
            pipeline_version="spacy-baseline-v1",
            model_name="en_core_web_sm",
            model_version="3.8.0",
            extractor_version="dependency-relations-v1",
            resolver_version="deterministic-org-aliases-v1",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            source_count=2,
            source_ids=["src_a", "src_b"],
            span_count=2,
            entity_count=4,
            relation_count=3,
        ),
        entities=[
            entity("ent_microsoft", "Microsoft", ["src_a", "src_b"]),
            entity("ent_github", "GitHub", ["src_a", "src_b"]),
            entity("ent_openai", "OpenAI", ["src_a"]),
            entity("ent_twitch", "Twitch", ["src_b"]),
        ],
        relations=[
            relation("rel_shared", "ent_microsoft", "ent_github", ["src_a", "src_b"]),
            relation("rel_a", "ent_github", "ent_openai", ["src_a"]),
            relation("rel_b", "ent_microsoft", "ent_twitch", ["src_b"]),
        ],
    )


def test_comparison_distinguishes_corroboration_from_single_source_evidence() -> None:
    comparison = build_source_comparison(
        analysis_fixture(),
        source_documents={
            "src_a": source("src_a", "source-a.txt"),
            "src_b": source("src_b", "source-b.txt"),
        },
    )

    assert comparison.comparison_version == "source-corroboration-v1"
    assert comparison.summary.source_count == 2
    assert comparison.summary.claim_count == 3
    assert comparison.summary.cross_source_claim_count == 1
    assert comparison.summary.single_source_claim_count == 2
    assert comparison.summary.pair_count == 1

    shared = next(claim for claim in comparison.claims if claim.relation_id == "rel_shared")
    assert shared.support_level == ClaimSupportLevel.CROSS_SOURCE
    assert shared.source_count == 2
    assert shared.evidence_count == 2
    assert shared.source_ids == ["src_a", "src_b"]

    unique = next(claim for claim in comparison.claims if claim.relation_id == "rel_a")
    assert unique.support_level == ClaimSupportLevel.SINGLE_SOURCE
    assert unique.source_count == 1

    overlap = comparison.overlaps[0]
    assert overlap.shared_claim_count == 1
    assert overlap.union_claim_count == 3
    assert overlap.jaccard_similarity == 1 / 3
    assert overlap.shared_relation_ids == ["rel_shared"]
    assert "not a contradiction" in comparison.interpretation_note


def test_comparison_profiles_include_sources_with_zero_claims() -> None:
    analysis = analysis_fixture()
    analysis.run.source_count = 3
    analysis.run.source_ids.append("src_empty")

    comparison = build_source_comparison(
        analysis,
        source_documents={
            "src_a": source("src_a", "source-a.txt"),
            "src_b": source("src_b", "source-b.txt"),
            "src_empty": source("src_empty", "empty.txt"),
        },
    )

    empty = next(profile for profile in comparison.sources if profile.source_id == "src_empty")
    assert empty.claim_count == 0
    assert empty.cross_source_claim_count == 0
    assert empty.single_source_claim_count == 0
    assert comparison.summary.source_count == 3
    assert comparison.summary.pair_count == 3
