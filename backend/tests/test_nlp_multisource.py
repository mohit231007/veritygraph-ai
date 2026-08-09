from app.domain.source import SourceBundle, SourceDocument, SourceSpan, SourceType
from app.nlp.engine import SpacyNlpEngine


def bundle(source_id: str, text: str) -> SourceBundle:
    document = SourceDocument(
        source_id=source_id,
        source_type=SourceType.DOCUMENT,
        title=source_id,
        filename=f"{source_id}.txt",
        source_format="txt",
        mime_type="text/plain",
        content_hash=(source_id[-1] * 64)[:64],
        size_bytes=len(text.encode("utf-8")),
        metadata={"span_count": 1},
    )
    span = SourceSpan(
        span_id=f"span_{source_id}",
        source_id=source_id,
        text=text,
        page_number=1,
        paragraph_number=1,
        char_start=0,
        char_end=len(text),
    )
    return SourceBundle(document=document, spans=[span])


def test_same_relation_across_sources_aggregates_evidence() -> None:
    engine = SpacyNlpEngine()
    entities, relations = engine.extract(
        run_id="run_cross_source",
        bundles=[
            bundle("src_1", "Microsoft acquired GitHub in 2018."),
            bundle("src_2", "GitHub was acquired by Microsoft in 2018."),
        ],
    )
    names = {entity.entity_id: entity.canonical_name for entity in entities}

    acquisition = next(
        relation
        for relation in relations
        if names[relation.subject_entity_id] == "Microsoft"
        and names[relation.object_entity_id] == "GitHub"
        and relation.predicate == "acquire"
    )

    assert acquisition.extraction_score == 0.92
    assert acquisition.extraction_method == "dependency_subject_object"
    assert len(acquisition.evidence) == 2
    assert {evidence.source_id for evidence in acquisition.evidence} == {"src_1", "src_2"}
