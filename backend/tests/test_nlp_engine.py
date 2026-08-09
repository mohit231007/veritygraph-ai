from app.domain.analysis import AssertionModality, AssertionPolarity
from app.domain.source import SourceBundle, SourceDocument, SourceSpan, SourceType
from app.nlp.engine import SpacyNlpEngine


def bundle(source_id: str, span_id: str, text: str) -> SourceBundle:
    document = SourceDocument(
        source_id=source_id,
        source_type=SourceType.DOCUMENT,
        title=source_id,
        filename=f"{source_id}.txt",
        source_format="txt",
        mime_type="text/plain",
        content_hash="b" * 64,
        size_bytes=len(text.encode("utf-8")),
        metadata={"span_count": 1},
    )
    span = SourceSpan(
        span_id=span_id,
        source_id=source_id,
        text=text,
        page_number=1,
        paragraph_number=1,
        char_start=0,
        char_end=len(text),
    )
    return SourceBundle(document=document, spans=[span])


def entity_by_name(entities, name: str):
    return next(
        entity
        for entity in entities
        if entity.canonical_name.casefold() == name.casefold()
    )


def test_spacy_engine_extracts_active_relation_with_exact_qualifiers_and_evidence() -> None:
    text = "Microsoft acquired GitHub in 2018."
    engine = SpacyNlpEngine()

    entities, relations = engine.extract(
        run_id="run_active",
        bundles=[bundle("src_active", "span_active", text)],
    )

    microsoft = entity_by_name(entities, "Microsoft")
    github = entity_by_name(entities, "GitHub")
    relation = next(
        item
        for item in relations
        if item.subject_entity_id == microsoft.entity_id
        and item.object_entity_id == github.entity_id
        and item.predicate == "acquire"
    )

    assert relation.polarity == AssertionPolarity.AFFIRMED
    assert relation.modality == AssertionModality.ASSERTED
    assert relation.modality_method == "dependency_no_modal_auxiliary_v1"
    assert relation.temporal_years == [2018]
    assert relation.temporal_method == "sentence_year_regex_v1"
    assert relation.extraction_score == 0.92
    assert relation.evidence[0].span_id == "span_active"
    assert relation.evidence[0].text == text


def test_spacy_engine_normalizes_passive_voice_to_semantic_direction() -> None:
    text = "GitHub was acquired by Microsoft in 2018."
    engine = SpacyNlpEngine()

    entities, relations = engine.extract(
        run_id="run_passive",
        bundles=[bundle("src_passive", "span_passive", text)],
    )

    microsoft = entity_by_name(entities, "Microsoft")
    github = entity_by_name(entities, "GitHub")
    relation = next(
        item
        for item in relations
        if item.subject_entity_id == microsoft.entity_id
        and item.object_entity_id == github.entity_id
        and item.predicate == "acquire"
    )

    assert relation.polarity == AssertionPolarity.AFFIRMED
    assert relation.modality == AssertionModality.ASSERTED
    assert relation.temporal_years == [2018]
    assert relation.extraction_method == "dependency_passive_agent"


def test_spacy_engine_marks_explicit_root_negation_without_rewriting_predicate() -> None:
    text = "Microsoft did not acquire GitHub."
    engine = SpacyNlpEngine()

    entities, relations = engine.extract(
        run_id="run_negated",
        bundles=[bundle("src_negated", "span_negated", text)],
    )

    microsoft = entity_by_name(entities, "Microsoft")
    github = entity_by_name(entities, "GitHub")
    relation = next(
        item
        for item in relations
        if item.subject_entity_id == microsoft.entity_id
        and item.object_entity_id == github.entity_id
        and item.predicate == "acquire"
    )

    assert relation.polarity == AssertionPolarity.NEGATED
    assert relation.modality == AssertionModality.ASSERTED
    assert relation.evidence[0].text == text


def test_spacy_engine_marks_modal_or_future_assertion_without_treating_it_as_asserted() -> None:
    text = "Microsoft may acquire GitHub in 2027."
    engine = SpacyNlpEngine()

    entities, relations = engine.extract(
        run_id="run_modal",
        bundles=[bundle("src_modal", "span_modal", text)],
    )

    microsoft = entity_by_name(entities, "Microsoft")
    github = entity_by_name(entities, "GitHub")
    relation = next(
        item
        for item in relations
        if item.subject_entity_id == microsoft.entity_id
        and item.object_entity_id == github.entity_id
        and item.predicate == "acquire"
    )

    assert relation.polarity == AssertionPolarity.AFFIRMED
    assert relation.modality == AssertionModality.MODAL
    assert relation.modality_method == "dependency_modal_auxiliary_v1"
    assert relation.temporal_years == [2027]


def test_spacy_engine_keeps_qualifier_variants_separate() -> None:
    engine = SpacyNlpEngine()
    bundles = [
        bundle("src_2018", "span_2018", "Microsoft acquired GitHub in 2018."),
        bundle("src_2019", "span_2019", "Microsoft acquired GitHub in 2019."),
        bundle("src_modal", "span_modal", "Microsoft may acquire GitHub in 2027."),
    ]

    entities, relations = engine.extract(run_id="run_qualifiers", bundles=bundles)
    microsoft = entity_by_name(entities, "Microsoft")
    github = entity_by_name(entities, "GitHub")
    matching = [
        relation
        for relation in relations
        if relation.subject_entity_id == microsoft.entity_id
        and relation.object_entity_id == github.entity_id
        and relation.predicate == "acquire"
    ]

    assert len(matching) == 3
    assert {(relation.modality, tuple(relation.temporal_years)) for relation in matching} == {
        (AssertionModality.ASSERTED, (2018,)),
        (AssertionModality.ASSERTED, (2019,)),
        (AssertionModality.MODAL, (2027,)),
    }


def test_spacy_engine_consolidates_exact_entity_mentions_across_sources() -> None:
    engine = SpacyNlpEngine()
    bundles = [
        bundle("src_one", "span_one", "Microsoft acquired GitHub in 2018."),
        bundle("src_two", "span_two", "Microsoft invested in OpenAI."),
    ]

    entities, _relations = engine.extract(run_id="run_multi", bundles=bundles)

    microsoft = entity_by_name(entities, "Microsoft")
    assert microsoft.entity_type == "ORG"
    assert microsoft.mention_count == 2
    assert {mention.source_id for mention in microsoft.mentions} == {"src_one", "src_two"}
