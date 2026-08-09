from datetime import UTC, datetime

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
from app.domain.comparison import ClaimSupportLevel
from app.domain.source import SourceDocument, SourceType
from app.services.comparison import build_source_comparison


def source(
    source_id: str,
    filename: str,
    *,
    content_hash: str | None = None,
    url: str | None = None,
    source_type: SourceType = SourceType.DOCUMENT,
) -> SourceDocument:
    return SourceDocument(
        source_id=source_id,
        source_type=source_type,
        title=filename,
        filename=filename if source_type == SourceType.DOCUMENT else None,
        url=url,
        source_format="txt" if source_type == SourceType.DOCUMENT else "html",
        mime_type="text/plain" if source_type == SourceType.DOCUMENT else "text/html",
        content_hash=content_hash or source_id[-1] * 64,
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
    *,
    polarity: AssertionPolarity = AssertionPolarity.AFFIRMED,
    modality: AssertionModality = AssertionModality.ASSERTED,
    years: list[int] | None = None,
    shared_evidence_text: str | None = None,
) -> Relation:
    evidence = [
        RelationEvidence(
            evidence_id=f"ev_{relation_id}_{index}",
            relation_id=relation_id,
            source_id=source_id,
            span_id=f"span_{source_id}",
            text=shared_evidence_text or f"Evidence from {source_id}.",
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
            run_id="run_compare",
            workspace_id="ws_compare",
            status=AnalysisStatus.COMPLETED,
            pipeline_version="spacy-baseline-v1",
            model_name="en_core_web_sm",
            model_version="3.8.0",
            extractor_version="dependency-relations-v3-qualifiers",
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


def source_documents() -> dict[str, SourceDocument]:
    return {
        "src_a": source("src_a", "source-a.txt"),
        "src_b": source("src_b", "source-b.txt"),
    }


def test_comparison_distinguishes_exact_qualified_support() -> None:
    comparison = build_source_comparison(
        analysis_fixture(), source_documents=source_documents()
    )

    assert comparison.comparison_version == "source-corroboration-v4-relationships"
    assert comparison.summary.cross_source_claim_count == 1
    assert comparison.summary.single_source_claim_count == 2
    assert comparison.summary.contradiction_candidate_count == 0
    assert comparison.summary.possible_derivation_pair_count == 0

    shared = next(claim for claim in comparison.claims if claim.relation_id == "rel_shared")
    assert shared.support_level == ClaimSupportLevel.CROSS_SOURCE
    assert shared.polarity == AssertionPolarity.AFFIRMED
    assert shared.modality == AssertionModality.ASSERTED
    assert shared.temporal_years == []
    assert shared.source_count == 2
    assert shared.distinct_content_fingerprint_count == 2
    assert shared.distinct_evidence_text_count == 2


def test_exact_duplicate_content_and_evidence_are_review_signals_not_independence_claims() -> None:
    analysis = analysis_fixture()
    analysis.relations = [
        relation(
            "rel_shared",
            "ent_microsoft",
            "ent_github",
            ["src_a", "src_b"],
            shared_evidence_text="Microsoft acquired GitHub.",
        )
    ]
    documents = {
        "src_a": source("src_a", "copy-a.txt", content_hash="f" * 64),
        "src_b": source("src_b", "copy-b.txt", content_hash="f" * 64),
    }

    comparison = build_source_comparison(analysis, source_documents=documents)

    claim = comparison.claims[0]
    assert claim.source_count == 2
    assert claim.distinct_content_fingerprint_count == 1
    assert claim.distinct_evidence_text_count == 1

    signal = comparison.source_relationships[0]
    assert signal.exact_content_fingerprint_match is True
    assert signal.exact_evidence_text_overlap_count == 1
    assert signal.exact_evidence_relation_ids == ["rel_shared"]
    assert signal.possible_derivation_signal is True
    assert "matching persisted content fingerprint" in signal.review_reasons
    assert comparison.summary.exact_content_match_pair_count == 1
    assert comparison.summary.exact_evidence_overlap_pair_count == 1
    assert comparison.summary.possible_derivation_pair_count == 1
    assert "does not prove" in comparison.interpretation_note


def test_same_origin_host_is_context_signal_but_not_proof_of_derivation() -> None:
    analysis = analysis_fixture()
    documents = {
        "src_a": source(
            "src_a",
            "page-a",
            url="https://www.example.com/reports/a",
            source_type=SourceType.PUBLIC_URL,
        ),
        "src_b": source(
            "src_b",
            "page-b",
            url="https://example.com/reports/b",
            source_type=SourceType.PUBLIC_URL,
        ),
    }

    comparison = build_source_comparison(analysis, source_documents=documents)

    signal = comparison.source_relationships[0]
    assert signal.left_origin_host == "example.com"
    assert signal.right_origin_host == "example.com"
    assert signal.same_origin_host is True
    assert signal.possible_derivation_signal is False
    assert signal.review_reasons == ["same origin host: example.com"]
    assert comparison.summary.same_origin_pair_count == 1
    assert comparison.summary.possible_derivation_pair_count == 0


def test_same_year_asserted_opposing_polarity_creates_candidate() -> None:
    analysis = analysis_fixture()
    analysis.relations = [
        relation("rel_yes", "ent_microsoft", "ent_github", ["src_a"], years=[2018]),
        relation(
            "rel_no",
            "ent_microsoft",
            "ent_github",
            ["src_b"],
            polarity=AssertionPolarity.NEGATED,
            years=[2018],
        ),
    ]

    comparison = build_source_comparison(analysis, source_documents=source_documents())

    assert comparison.summary.contradiction_candidate_count == 1
    candidate = comparison.contradictions[0]
    assert candidate.temporal_years == [2018]
    assert candidate.affirmed_relation_ids == ["rel_yes"]
    assert candidate.negated_relation_ids == ["rel_no"]


def test_disjoint_years_do_not_create_false_contradiction() -> None:
    analysis = analysis_fixture()
    analysis.relations = [
        relation("rel_yes", "ent_microsoft", "ent_github", ["src_a"], years=[2018]),
        relation(
            "rel_no",
            "ent_microsoft",
            "ent_github",
            ["src_b"],
            polarity=AssertionPolarity.NEGATED,
            years=[2019],
        ),
    ]

    comparison = build_source_comparison(analysis, source_documents=source_documents())
    assert comparison.summary.contradiction_candidate_count == 0
    assert comparison.contradictions == []


def test_one_sided_time_scope_does_not_create_false_contradiction() -> None:
    analysis = analysis_fixture()
    analysis.relations = [
        relation("rel_yes", "ent_microsoft", "ent_github", ["src_a"], years=[2018]),
        relation(
            "rel_no",
            "ent_microsoft",
            "ent_github",
            ["src_b"],
            polarity=AssertionPolarity.NEGATED,
        ),
    ]

    comparison = build_source_comparison(analysis, source_documents=source_documents())
    assert comparison.summary.contradiction_candidate_count == 0


def test_modal_language_does_not_create_contradiction_candidate() -> None:
    analysis = analysis_fixture()
    analysis.relations = [
        relation(
            "rel_modal",
            "ent_microsoft",
            "ent_github",
            ["src_a"],
            modality=AssertionModality.MODAL,
            years=[2027],
        ),
        relation(
            "rel_no",
            "ent_microsoft",
            "ent_github",
            ["src_b"],
            polarity=AssertionPolarity.NEGATED,
            years=[2027],
        ),
    ]

    comparison = build_source_comparison(analysis, source_documents=source_documents())
    assert comparison.summary.contradiction_candidate_count == 0


def test_unknown_historical_qualifiers_never_create_contradiction_candidate() -> None:
    analysis = analysis_fixture()
    unknown = relation("rel_unknown", "ent_microsoft", "ent_github", ["src_b"])
    unknown.polarity = AssertionPolarity.UNKNOWN
    unknown.polarity_method = "historical_unknown"
    unknown.modality = AssertionModality.UNKNOWN
    unknown.modality_method = "historical_unknown"
    unknown.temporal_method = "historical_unknown"
    analysis.relations = [
        relation("rel_yes", "ent_microsoft", "ent_github", ["src_a"]),
        unknown,
    ]

    comparison = build_source_comparison(analysis, source_documents=source_documents())
    assert comparison.summary.contradiction_candidate_count == 0


def test_comparison_profiles_include_sources_with_zero_claims() -> None:
    analysis = analysis_fixture()
    analysis.run.source_count = 3
    analysis.run.source_ids.append("src_empty")

    comparison = build_source_comparison(
        analysis,
        source_documents={
            **source_documents(),
            "src_empty": source("src_empty", "empty.txt"),
        },
    )

    empty = next(profile for profile in comparison.sources if profile.source_id == "src_empty")
    assert empty.claim_count == 0
    assert empty.contradiction_candidate_count == 0
    assert comparison.summary.source_count == 3
    assert comparison.summary.pair_count == 3
    assert len(comparison.source_relationships) == 3
