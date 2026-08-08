from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from uuid import uuid4

import spacy
from spacy.language import Language
from spacy.tokens import Span, Token

from app.domain.analysis import Entity, EntityMention, Relation, RelationEvidence
from app.domain.source import SourceBundle, SourceSpan

DEFAULT_ENTITY_LABELS = {
    "PERSON",
    "ORG",
    "GPE",
    "LOC",
    "FAC",
    "PRODUCT",
    "EVENT",
    "NORP",
    "LAW",
    "WORK_OF_ART",
}

SUBJECT_DEPS = {"nsubj", "nsubjpass", "csubj", "csubjpass"}
PASSIVE_SUBJECT_DEPS = {"nsubjpass", "csubjpass"}
DIRECT_OBJECT_DEPS = {"dobj", "obj", "attr", "oprd", "dative"}


@dataclass(slots=True)
class SpanDocument:
    source_span: SourceSpan
    document: object


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _normalize_entity(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    value = re.sub(r"[^\w\s-]", " ", value)
    return " ".join(value.split())


def _entity_key(ent: Span) -> str:
    return f"{ent.label_}:{_normalize_entity(ent.text)}"


def _predicate(root: Token, prep: Token | None = None) -> str:
    lemma = root.lemma_.strip().lower() or root.text.strip().lower()
    particles = [
        child.lemma_.strip().lower() or child.text.strip().lower()
        for child in root.children
        if child.dep_ == "prt"
    ]
    parts = [lemma, *particles]
    if prep is not None:
        parts.append(prep.lemma_.strip().lower() or prep.text.strip().lower())
    return " ".join(part for part in parts if part)


def _sentence_evidence(
    *,
    relation_id: str,
    source_span: SourceSpan,
    sentence: Span,
) -> RelationEvidence:
    return RelationEvidence(
        evidence_id=_id("ev"),
        relation_id=relation_id,
        source_id=source_span.source_id,
        span_id=source_span.span_id,
        text=sentence.text.strip(),
        sentence_start=sentence.start_char,
        sentence_end=sentence.end_char,
    )


class SpacyNlpEngine:
    """Free local spaCy baseline for NER and dependency-based relations.

    Relation scores are transparent extraction-rule scores. They are not calibrated
    probabilities and must not be presented to users as factual confidence.
    """

    PIPELINE_VERSION = "spacy-baseline-v1"
    EXTRACTOR_VERSION = "dependency-relations-v1"

    def __init__(
        self,
        model_name: str = "en_core_web_sm",
        *,
        entity_labels: set[str] | None = None,
        batch_size: int = 64,
    ) -> None:
        self.model_name = model_name
        self.nlp: Language = spacy.load(model_name)
        self.model_version = str(self.nlp.meta.get("version", "unknown"))
        self.entity_labels = entity_labels or DEFAULT_ENTITY_LABELS
        self.batch_size = batch_size

    def extract(
        self,
        *,
        run_id: str,
        bundles: Iterable[SourceBundle],
    ) -> tuple[list[Entity], list[Relation]]:
        source_spans = [span for bundle in bundles for span in bundle.spans]
        if not source_spans:
            return [], []

        documents = list(
            self.nlp.pipe(
                (span.text for span in source_spans),
                batch_size=self.batch_size,
            )
        )
        span_documents = [
            SpanDocument(source_span=source_span, document=document)
            for source_span, document in zip(source_spans, documents, strict=True)
        ]

        entities, mention_index = self._entities(run_id, span_documents)
        relations = self._relations(run_id, span_documents, mention_index)
        return entities, relations

    def _entities(
        self,
        run_id: str,
        span_documents: list[SpanDocument],
    ) -> tuple[list[Entity], dict[tuple[str, int, int], str]]:
        grouped_mentions: dict[str, list[EntityMention]] = defaultdict(list)
        canonical_names: dict[str, str] = {}
        entity_types: dict[str, str] = {}
        entity_ids: dict[str, str] = {}
        mention_index: dict[tuple[str, int, int], str] = {}

        for item in span_documents:
            source_span = item.source_span
            document = item.document
            for ent in document.ents:
                if ent.label_ not in self.entity_labels:
                    continue
                key = _entity_key(ent)
                if key.endswith(":"):
                    continue
                entity_id = entity_ids.setdefault(key, _id("ent"))
                canonical_names.setdefault(key, ent.text.strip())
                entity_types.setdefault(key, ent.label_)
                mention = EntityMention(
                    mention_id=_id("men"),
                    entity_id=entity_id,
                    source_id=source_span.source_id,
                    span_id=source_span.span_id,
                    text=ent.text,
                    start_char=ent.start_char,
                    end_char=ent.end_char,
                )
                grouped_mentions[key].append(mention)
                mention_index[(source_span.span_id, ent.start_char, ent.end_char)] = entity_id

        entities = [
            Entity(
                entity_id=entity_ids[key],
                run_id=run_id,
                canonical_name=canonical_names[key],
                entity_type=entity_types[key],
                normalized_key=key,
                mention_count=len(mentions),
                mentions=mentions,
            )
            for key, mentions in grouped_mentions.items()
        ]
        entities.sort(key=lambda entity: (-entity.mention_count, entity.canonical_name.casefold()))
        return entities, mention_index

    def _relations(
        self,
        run_id: str,
        span_documents: list[SpanDocument],
        mention_index: dict[tuple[str, int, int], str],
    ) -> list[Relation]:
        aggregated: dict[tuple[str, str, str], Relation] = {}
        evidence_keys: dict[str, set[tuple[str, int, int]]] = defaultdict(set)

        for item in span_documents:
            source_span = item.source_span
            document = item.document
            for sentence in document.sents:
                sentence_entities = [
                    ent for ent in document.ents if ent.label_ in self.entity_labels and ent.sent == sentence
                ]
                if len(sentence_entities) < 2:
                    continue

                entity_id_by_span = {
                    (ent.start_char, ent.end_char): mention_index.get(
                        (source_span.span_id, ent.start_char, ent.end_char)
                    )
                    for ent in sentence_entities
                }
                root = sentence.root
                subjects = [
                    ent
                    for ent in sentence_entities
                    if ent.root.dep_ in SUBJECT_DEPS and ent.root.head == root
                ]
                active_subjects = [
                    ent for ent in subjects if ent.root.dep_ not in PASSIVE_SUBJECT_DEPS
                ]
                passive_subjects = [
                    ent for ent in subjects if ent.root.dep_ in PASSIVE_SUBJECT_DEPS
                ]
                direct_objects = [
                    ent
                    for ent in sentence_entities
                    if ent.root.dep_ in DIRECT_OBJECT_DEPS and ent.root.head == root
                ]
                prep_objects = [
                    (ent, ent.root.head)
                    for ent in sentence_entities
                    if ent.root.dep_ == "pobj"
                    and ent.root.head.dep_ in {"prep", "agent"}
                    and ent.root.head.head == root
                ]

                for subject in active_subjects:
                    for obj in direct_objects:
                        self._add_relation(
                            aggregated=aggregated,
                            evidence_keys=evidence_keys,
                            run_id=run_id,
                            source_span=source_span,
                            sentence=sentence,
                            subject_id=entity_id_by_span[(subject.start_char, subject.end_char)],
                            predicate=_predicate(root),
                            object_id=entity_id_by_span[(obj.start_char, obj.end_char)],
                            extraction_score=0.92,
                            extraction_method="dependency_subject_object",
                        )

                    for obj, prep in prep_objects:
                        if prep.dep_ == "agent":
                            continue
                        self._add_relation(
                            aggregated=aggregated,
                            evidence_keys=evidence_keys,
                            run_id=run_id,
                            source_span=source_span,
                            sentence=sentence,
                            subject_id=entity_id_by_span[(subject.start_char, subject.end_char)],
                            predicate=_predicate(root, prep),
                            object_id=entity_id_by_span[(obj.start_char, obj.end_char)],
                            extraction_score=0.84,
                            extraction_method="dependency_subject_preposition_object",
                        )

                agent_objects = [
                    (ent, prep)
                    for ent, prep in prep_objects
                    if prep.dep_ == "agent" or prep.lemma_.lower() == "by"
                ]
                for passive_object in passive_subjects:
                    for agent, _prep in agent_objects:
                        self._add_relation(
                            aggregated=aggregated,
                            evidence_keys=evidence_keys,
                            run_id=run_id,
                            source_span=source_span,
                            sentence=sentence,
                            subject_id=entity_id_by_span[(agent.start_char, agent.end_char)],
                            predicate=_predicate(root),
                            object_id=entity_id_by_span[
                                (passive_object.start_char, passive_object.end_char)
                            ],
                            extraction_score=0.90,
                            extraction_method="dependency_passive_agent",
                        )

        relations = list(aggregated.values())
        relations.sort(key=lambda relation: (-relation.extraction_score, relation.predicate))
        return relations

    @staticmethod
    def _add_relation(
        *,
        aggregated: dict[tuple[str, str, str], Relation],
        evidence_keys: dict[str, set[tuple[str, int, int]]],
        run_id: str,
        source_span: SourceSpan,
        sentence: Span,
        subject_id: str | None,
        predicate: str,
        object_id: str | None,
        extraction_score: float,
        extraction_method: str,
    ) -> None:
        if not subject_id or not object_id or subject_id == object_id or not predicate:
            return
        key = (subject_id, predicate, object_id)
        relation = aggregated.get(key)
        if relation is None:
            relation = Relation(
                relation_id=_id("rel"),
                run_id=run_id,
                subject_entity_id=subject_id,
                predicate=predicate,
                object_entity_id=object_id,
                extraction_score=extraction_score,
                extraction_method=extraction_method,
                evidence=[],
            )
            aggregated[key] = relation
        elif extraction_score > relation.extraction_score:
            relation.extraction_score = extraction_score
            relation.extraction_method = extraction_method

        evidence_key = (source_span.span_id, sentence.start_char, sentence.end_char)
        if evidence_key in evidence_keys[relation.relation_id]:
            return
        evidence_keys[relation.relation_id].add(evidence_key)
        relation.evidence.append(
            _sentence_evidence(
                relation_id=relation.relation_id,
                source_span=source_span,
                sentence=sentence,
            )
        )
