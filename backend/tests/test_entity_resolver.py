from app.domain.analysis import Entity, EntityMention, Relation, RelationEvidence
from app.nlp.resolver import DeterministicEntityResolver


def make_entity(
    entity_id: str,
    name: str,
    *,
    entity_type: str = "ORG",
    source_id: str | None = None,
) -> Entity:
    source = source_id or f"src_{entity_id}"
    mention = EntityMention(
        mention_id=f"men_{entity_id}",
        entity_id=entity_id,
        source_id=source,
        span_id=f"span_{entity_id}",
        text=name,
        start_char=0,
        end_char=len(name),
    )
    return Entity(
        entity_id=entity_id,
        run_id="run_resolver",
        canonical_name=name,
        entity_type=entity_type,
        normalized_key=f"{entity_type}:{name.casefold()}",
        mention_count=1,
        mentions=[mention],
    )


def make_relation(
    relation_id: str,
    subject_id: str,
    object_id: str,
    *,
    predicate: str = "acquire",
    source_id: str,
) -> Relation:
    evidence = RelationEvidence(
        evidence_id=f"ev_{relation_id}",
        relation_id=relation_id,
        source_id=source_id,
        span_id=f"span_{source_id}",
        text=f"Evidence from {source_id}.",
        sentence_start=0,
        sentence_end=24,
    )
    return Relation(
        relation_id=relation_id,
        run_id="run_resolver",
        subject_entity_id=subject_id,
        predicate=predicate,
        object_entity_id=object_id,
        extraction_score=0.92,
        extraction_method="dependency_subject_object",
        evidence=[evidence],
    )


def test_resolver_merges_unique_acronym_suffixes_and_relation_evidence() -> None:
    resolver = DeterministicEntityResolver()
    entities = [
        make_entity("ent_full", "International Business Machines", source_id="src_full"),
        make_entity("ent_acronym", "IBM", source_id="src_acronym"),
        make_entity("ent_suffix", "IBM Corp.", source_id="src_suffix"),
        make_entity("ent_target", "Red Hat", source_id="src_target"),
    ]
    relations = [
        make_relation(
            "rel_full",
            "ent_full",
            "ent_target",
            source_id="src_full",
        ),
        make_relation(
            "rel_acronym",
            "ent_acronym",
            "ent_target",
            source_id="src_acronym",
        ),
    ]

    resolved_entities, resolved_relations = resolver.resolve(
        entities=entities,
        relations=relations,
    )

    ibm = next(
        entity
        for entity in resolved_entities
        if entity.canonical_name == "International Business Machines"
    )
    assert ibm.mention_count == 3
    assert {mention.text for mention in ibm.mentions} == {
        "International Business Machines",
        "IBM",
        "IBM Corp.",
    }
    assert {mention.entity_id for mention in ibm.mentions} == {ibm.entity_id}
    assert ibm.normalized_key == "ORG:international business machines"
    assert len(resolved_entities) == 2

    assert len(resolved_relations) == 1
    relation = resolved_relations[0]
    assert relation.subject_entity_id == ibm.entity_id
    assert relation.object_entity_id == "ent_target"
    assert len(relation.evidence) == 2
    assert {item.source_id for item in relation.evidence} == {"src_full", "src_acronym"}
    assert {item.relation_id for item in relation.evidence} == {relation.relation_id}


def test_resolver_prefers_suffix_free_organization_name() -> None:
    resolver = DeterministicEntityResolver()
    entities = [
        make_entity("ent_short", "Microsoft"),
        make_entity("ent_legal", "Microsoft Corporation"),
    ]

    resolved_entities, _ = resolver.resolve(entities=entities, relations=[])

    assert len(resolved_entities) == 1
    assert resolved_entities[0].canonical_name == "Microsoft"
    assert resolved_entities[0].mention_count == 2


def test_resolver_keeps_ambiguous_acronym_separate() -> None:
    resolver = DeterministicEntityResolver()
    entities = [
        make_entity("ent_one", "International Business Machines"),
        make_entity("ent_two", "Institute of Business Management"),
        make_entity("ent_acronym", "IBM"),
    ]

    resolved_entities, _ = resolver.resolve(entities=entities, relations=[])

    assert len(resolved_entities) == 3
    assert {entity.canonical_name for entity in resolved_entities} == {
        "International Business Machines",
        "Institute of Business Management",
        "IBM",
    }


def test_resolver_drops_relation_that_becomes_self_loop_after_alias_merge() -> None:
    resolver = DeterministicEntityResolver()
    entities = [
        make_entity("ent_short", "Microsoft"),
        make_entity("ent_legal", "Microsoft Corporation"),
    ]
    relations = [
        make_relation(
            "rel_alias",
            "ent_short",
            "ent_legal",
            predicate="alias of",
            source_id="src_alias",
        )
    ]

    _, resolved_relations = resolver.resolve(entities=entities, relations=relations)

    assert resolved_relations == []


def test_resolver_does_not_merge_non_organization_acronyms() -> None:
    resolver = DeterministicEntityResolver()
    entities = [
        make_entity("ent_full", "Artificial Intelligence", entity_type="WORK_OF_ART"),
        make_entity("ent_short", "AI", entity_type="WORK_OF_ART"),
    ]

    resolved_entities, _ = resolver.resolve(entities=entities, relations=[])

    assert len(resolved_entities) == 2
