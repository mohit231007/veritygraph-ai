from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from app.domain.analysis import (
    AssertionModality,
    AssertionPolarity,
    Entity,
    Relation,
    RelationEvidence,
)

CORPORATE_SUFFIXES = {
    "ag",
    "co",
    "company",
    "corp",
    "corporation",
    "gmbh",
    "inc",
    "incorporated",
    "limited",
    "llc",
    "ltd",
    "plc",
    "sa",
}
INITIALISM_STOPWORDS = {"and", "for", "of", "the"}


def _words(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)


def _legal_root(text: str) -> str:
    tokens = _words(text)
    while len(tokens) > 1 and tokens[-1] in CORPORATE_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _compact_acronym(text: str) -> str | None:
    compact = re.sub(r"[^A-Za-z0-9]", "", text)
    if not 2 <= len(compact) <= 10:
        return None
    if not any(character.isalpha() for character in compact):
        return None
    return compact if compact.isupper() else None


def _initialism(text: str) -> str | None:
    tokens = [token for token in _legal_root(text).split() if token not in INITIALISM_STOPWORDS]
    if len(tokens) < 2:
        return None
    value = "".join(token[0] for token in tokens).upper()
    return value if 2 <= len(value) <= 10 else None


def _has_corporate_suffix(text: str) -> bool:
    tokens = _words(text)
    return bool(tokens) and tokens[-1] in CORPORATE_SUFFIXES


class _UnionFind:
    def __init__(self, entity_ids: list[str]) -> None:
        self.parent = {entity_id: entity_id for entity_id in entity_ids}

    def find(self, entity_id: str) -> str:
        parent = self.parent[entity_id]
        if parent != entity_id:
            self.parent[entity_id] = self.find(parent)
        return self.parent[entity_id]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


class DeterministicEntityResolver:
    """Conservative local alias resolver for organization entities.

    The baseline deliberately resolves only transparent cases:
    - organization names that differ only by a trailing legal suffix;
    - an uppercase acronym when exactly one multi-token organization expands to it.

    It does not use embeddings, fuzzy distance, web lookup, or an LLM. Ambiguous
    acronym matches remain separate entities rather than being guessed.
    """

    VERSION = "deterministic-org-aliases-v1"

    def resolve(
        self,
        *,
        entities: list[Entity],
        relations: list[Relation],
    ) -> tuple[list[Entity], list[Relation]]:
        if not entities:
            return [], relations

        by_id = {entity.entity_id: entity for entity in entities}
        union_find = _UnionFind(list(by_id))
        organizations = [entity for entity in entities if entity.entity_type == "ORG"]

        self._merge_legal_suffix_variants(organizations, union_find)
        self._merge_unique_acronyms(organizations, union_find)

        groups: dict[str, list[Entity]] = defaultdict(list)
        for entity in entities:
            groups[union_find.find(entity.entity_id)].append(entity)

        entity_id_map: dict[str, str] = {}
        resolved_entities: list[Entity] = []
        for group in groups.values():
            canonical = min(group, key=self._canonical_rank)
            canonical_id = canonical.entity_id
            for member in group:
                entity_id_map[member.entity_id] = canonical_id

            mentions = [
                mention.model_copy(update={"entity_id": canonical_id})
                for member in group
                for mention in member.mentions
            ]
            mentions.sort(key=lambda item: (item.source_id, item.span_id, item.start_char))
            normalized_key = canonical.normalized_key
            if canonical.entity_type == "ORG":
                normalized_key = f"ORG:{_legal_root(canonical.canonical_name)}"

            resolved_entities.append(
                Entity(
                    entity_id=canonical_id,
                    run_id=canonical.run_id,
                    canonical_name=canonical.canonical_name,
                    entity_type=canonical.entity_type,
                    normalized_key=normalized_key,
                    mention_count=len(mentions),
                    mentions=mentions,
                )
            )

        resolved_entities.sort(
            key=lambda entity: (-entity.mention_count, entity.canonical_name.casefold())
        )
        resolved_relations = self._remap_relations(relations, entity_id_map)
        return resolved_entities, resolved_relations

    @staticmethod
    def _merge_legal_suffix_variants(
        organizations: list[Entity],
        union_find: _UnionFind,
    ) -> None:
        by_root: dict[str, list[str]] = defaultdict(list)
        for entity in organizations:
            root = _legal_root(entity.canonical_name)
            if len(root) >= 2:
                by_root[root].append(entity.entity_id)

        for entity_ids in by_root.values():
            first = entity_ids[0]
            for entity_id in entity_ids[1:]:
                union_find.union(first, entity_id)

    @staticmethod
    def _merge_unique_acronyms(
        organizations: list[Entity],
        union_find: _UnionFind,
    ) -> None:
        ids_by_root: dict[str, list[str]] = defaultdict(list)
        roots_by_initialism: dict[str, set[str]] = defaultdict(set)
        for entity in organizations:
            root = _legal_root(entity.canonical_name)
            ids_by_root[root].append(entity.entity_id)
            if _compact_acronym(entity.canonical_name) is None:
                initialism = _initialism(entity.canonical_name)
                if initialism:
                    roots_by_initialism[initialism].add(root)

        for entity in organizations:
            acronym = _compact_acronym(entity.canonical_name)
            if acronym is None:
                continue
            candidate_roots = roots_by_initialism.get(acronym, set())
            if len(candidate_roots) != 1:
                continue
            candidate_root = next(iter(candidate_roots))
            candidate_ids = ids_by_root[candidate_root]
            if candidate_ids:
                union_find.union(candidate_ids[0], entity.entity_id)

    @staticmethod
    def _canonical_rank(entity: Entity) -> tuple[bool, bool, int, int, str]:
        return (
            _compact_acronym(entity.canonical_name) is not None,
            _has_corporate_suffix(entity.canonical_name),
            -entity.mention_count,
            len(entity.canonical_name),
            entity.canonical_name.casefold(),
        )

    @staticmethod
    def _remap_relations(
        relations: list[Relation],
        entity_id_map: dict[str, str],
    ) -> list[Relation]:
        aggregated: dict[
            tuple[
                str,
                str,
                str,
                AssertionPolarity,
                AssertionModality,
                tuple[int, ...],
            ],
            Relation,
        ] = {}
        evidence_seen: dict[str, set[tuple[str, str, int, int, str]]] = defaultdict(set)

        for relation in relations:
            subject_id = entity_id_map.get(
                relation.subject_entity_id,
                relation.subject_entity_id,
            )
            object_id = entity_id_map.get(
                relation.object_entity_id,
                relation.object_entity_id,
            )
            if subject_id == object_id:
                continue

            key = (
                subject_id,
                relation.predicate,
                object_id,
                relation.polarity,
                relation.modality,
                tuple(relation.temporal_years),
            )
            resolved = aggregated.get(key)
            if resolved is None:
                resolved = relation.model_copy(
                    deep=True,
                    update={
                        "subject_entity_id": subject_id,
                        "object_entity_id": object_id,
                        "evidence": [],
                    },
                )
                aggregated[key] = resolved
            elif relation.extraction_score > resolved.extraction_score:
                resolved.extraction_score = relation.extraction_score
                resolved.extraction_method = relation.extraction_method
                resolved.polarity_method = relation.polarity_method
                resolved.modality_method = relation.modality_method
                resolved.temporal_method = relation.temporal_method

            for evidence in relation.evidence:
                evidence_key = (
                    evidence.source_id,
                    evidence.span_id,
                    evidence.sentence_start,
                    evidence.sentence_end,
                    evidence.text,
                )
                if evidence_key in evidence_seen[resolved.relation_id]:
                    continue
                evidence_seen[resolved.relation_id].add(evidence_key)
                resolved.evidence.append(
                    RelationEvidence(
                        evidence_id=evidence.evidence_id,
                        relation_id=resolved.relation_id,
                        source_id=evidence.source_id,
                        span_id=evidence.span_id,
                        text=evidence.text,
                        sentence_start=evidence.sentence_start,
                        sentence_end=evidence.sentence_end,
                    )
                )

        resolved_relations = list(aggregated.values())
        resolved_relations.sort(
            key=lambda relation: (
                -relation.extraction_score,
                relation.predicate,
                relation.polarity.value,
                relation.modality.value,
                tuple(relation.temporal_years),
            )
        )
        return resolved_relations
