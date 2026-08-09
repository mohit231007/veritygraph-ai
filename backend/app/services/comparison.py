from __future__ import annotations

import unicodedata
from collections import defaultdict
from itertools import combinations
from urllib.parse import urlparse

from app.domain.analysis import (
    AssertionModality,
    AssertionPolarity,
    Relation,
    WorkspaceAnalysis,
)
from app.domain.comparison import (
    ClaimSupportLevel,
    ComparisonClaim,
    ContradictionCandidate,
    SourceClaimProfile,
    SourceComparison,
    SourceComparisonSummary,
    SourcePairOverlap,
    SourceRelationshipSignal,
)
from app.domain.source import SourceDocument

COMPARISON_VERSION = "source-corroboration-v4-relationships"
INTERPRETATION_NOTE = (
    "Cross-source means the same resolved qualified assertion has retained evidence from at "
    "least two distinct source IDs in this analysis run; it does not prove independent "
    "reporting. Exact content-fingerprint matches, same-origin hosts, and identical normalized "
    "supporting sentences are surfaced as source-relationship review signals. These signals "
    "do not prove that one source copied another, and their absence does not prove independence. "
    "Contradiction candidates still require asserted opposing polarity, compatible explicit "
    "time scope, and evidence from at least two distinct source IDs."
)


def _source_ids_for_run(analysis: WorkspaceAnalysis) -> list[str]:
    if analysis.run.source_ids:
        return list(dict.fromkeys(analysis.run.source_ids))

    discovered = [
        evidence.source_id
        for relation in analysis.relations
        for evidence in relation.evidence
    ]
    discovered.extend(
        mention.source_id
        for entity in analysis.entities
        for mention in entity.mentions
    )
    return list(dict.fromkeys(discovered))


def _assertion_key(relation: Relation) -> tuple[str, str, str]:
    return (
        relation.subject_entity_id,
        relation.predicate,
        relation.object_entity_id,
    )


def _compatible_years(left: Relation, right: Relation) -> list[int] | None:
    left_years = set(left.temporal_years)
    right_years = set(right.temporal_years)
    if not left_years and not right_years:
        return []
    if not left_years or not right_years:
        return None
    overlap = sorted(left_years & right_years)
    return overlap or None


def _normalize_evidence_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(value.split())


def _origin_host(document: SourceDocument | None) -> str | None:
    if document is None or not document.url:
        return None
    host = urlparse(document.url).hostname
    if not host:
        return None
    normalized = host.casefold().rstrip(".")
    return normalized[4:] if normalized.startswith("www.") else normalized


def _content_fingerprint(document: SourceDocument | None, source_id: str) -> str:
    if document is not None and document.content_hash:
        return f"content:{document.content_hash}"
    return f"source:{source_id}"


def build_source_comparison(
    analysis: WorkspaceAnalysis,
    *,
    source_documents: dict[str, SourceDocument],
) -> SourceComparison:
    """Compare qualified support and expose conservative source relationship signals."""

    entity_names = {entity.entity_id: entity.canonical_name for entity in analysis.entities}
    source_ids = _source_ids_for_run(analysis)
    source_order = {source_id: index for index, source_id in enumerate(source_ids)}

    claims: list[ComparisonClaim] = []
    claim_ids_by_source = {source_id: set() for source_id in source_ids}
    relations_by_assertion: dict[tuple[str, str, str], list[Relation]] = defaultdict(list)
    evidence_texts_by_relation_source: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )

    for relation in analysis.relations:
        relations_by_assertion[_assertion_key(relation)].append(relation)
        evidence_source_ids = list(
            dict.fromkeys(evidence.source_id for evidence in relation.evidence)
        )
        evidence_source_ids.sort(
            key=lambda source_id: (source_order.get(source_id, len(source_order)), source_id)
        )
        if not evidence_source_ids:
            continue

        normalized_evidence_texts = {
            _normalize_evidence_text(evidence.text)
            for evidence in relation.evidence
            if _normalize_evidence_text(evidence.text)
        }
        for evidence in relation.evidence:
            normalized = _normalize_evidence_text(evidence.text)
            if normalized:
                evidence_texts_by_relation_source[relation.relation_id][
                    evidence.source_id
                ].add(normalized)

        content_fingerprints = {
            _content_fingerprint(source_documents.get(source_id), source_id)
            for source_id in evidence_source_ids
        }
        support_level = (
            ClaimSupportLevel.CROSS_SOURCE
            if len(evidence_source_ids) >= 2
            else ClaimSupportLevel.SINGLE_SOURCE
        )
        claim = ComparisonClaim(
            relation_id=relation.relation_id,
            subject_entity_id=relation.subject_entity_id,
            subject_label=entity_names.get(relation.subject_entity_id, relation.subject_entity_id),
            predicate=relation.predicate,
            object_entity_id=relation.object_entity_id,
            object_label=entity_names.get(relation.object_entity_id, relation.object_entity_id),
            polarity=relation.polarity,
            polarity_method=relation.polarity_method,
            modality=relation.modality,
            modality_method=relation.modality_method,
            temporal_years=relation.temporal_years,
            temporal_method=relation.temporal_method,
            extraction_score=relation.extraction_score,
            support_level=support_level,
            source_count=len(evidence_source_ids),
            source_ids=evidence_source_ids,
            distinct_content_fingerprint_count=max(1, len(content_fingerprints)),
            distinct_evidence_text_count=max(1, len(normalized_evidence_texts)),
            evidence_count=len(relation.evidence),
            evidence=relation.evidence,
        )
        claims.append(claim)
        for source_id in evidence_source_ids:
            claim_ids_by_source.setdefault(source_id, set()).add(relation.relation_id)

    claims.sort(
        key=lambda claim: (
            claim.support_level != ClaimSupportLevel.CROSS_SOURCE,
            claim.distinct_content_fingerprint_count == claim.source_count,
            -claim.source_count,
            -claim.evidence_count,
            claim.subject_label.casefold(),
            claim.predicate,
            claim.object_label.casefold(),
            claim.polarity.value,
            claim.modality.value,
            tuple(claim.temporal_years),
        )
    )

    contradictions: list[ContradictionCandidate] = []
    candidate_keys_by_source: dict[str, set[str]] = defaultdict(set)
    for (subject_id, predicate, object_id), assertion_relations in relations_by_assertion.items():
        affirmed = [
            relation
            for relation in assertion_relations
            if relation.polarity == AssertionPolarity.AFFIRMED
            and relation.modality == AssertionModality.ASSERTED
        ]
        negated = [
            relation
            for relation in assertion_relations
            if relation.polarity == AssertionPolarity.NEGATED
            and relation.modality == AssertionModality.ASSERTED
        ]
        if not affirmed or not negated:
            continue

        compatible_pairs: list[tuple[Relation, Relation, list[int]]] = []
        for affirmed_relation in affirmed:
            for negated_relation in negated:
                compatible_years = _compatible_years(affirmed_relation, negated_relation)
                if compatible_years is not None:
                    compatible_pairs.append(
                        (affirmed_relation, negated_relation, compatible_years)
                    )
        if not compatible_pairs:
            continue

        compatible_affirmed = {
            relation.relation_id: relation
            for relation, _negated, _years in compatible_pairs
        }
        compatible_negated = {
            relation.relation_id: relation
            for _affirmed, relation, _years in compatible_pairs
        }
        compatible_year_sets = [set(years) for _left, _right, years in compatible_pairs if years]
        candidate_years = sorted(set().union(*compatible_year_sets)) if compatible_year_sets else []

        affirmed_evidence = [
            evidence
            for relation in compatible_affirmed.values()
            for evidence in relation.evidence
        ]
        negated_evidence = [
            evidence
            for relation in compatible_negated.values()
            for evidence in relation.evidence
        ]
        affirmed_source_ids = list(
            dict.fromkeys(evidence.source_id for evidence in affirmed_evidence)
        )
        negated_source_ids = list(
            dict.fromkeys(evidence.source_id for evidence in negated_evidence)
        )
        all_source_ids = list(dict.fromkeys([*affirmed_source_ids, *negated_source_ids]))
        if len(all_source_ids) < 2:
            continue

        affirmed_source_ids.sort(
            key=lambda source_id: (source_order.get(source_id, len(source_order)), source_id)
        )
        negated_source_ids.sort(
            key=lambda source_id: (source_order.get(source_id, len(source_order)), source_id)
        )
        year_key = ",".join(str(year) for year in candidate_years) or "unscoped"
        assertion_key = f"{subject_id}|{predicate}|{object_id}|{year_key}"
        candidate = ContradictionCandidate(
            assertion_key=assertion_key,
            subject_entity_id=subject_id,
            subject_label=entity_names.get(subject_id, subject_id),
            predicate=predicate,
            object_entity_id=object_id,
            object_label=entity_names.get(object_id, object_id),
            temporal_years=candidate_years,
            affirmed_relation_ids=sorted(compatible_affirmed),
            negated_relation_ids=sorted(compatible_negated),
            affirmed_source_ids=affirmed_source_ids,
            negated_source_ids=negated_source_ids,
            source_count=len(all_source_ids),
            evidence_count=len(affirmed_evidence) + len(negated_evidence),
            affirmed_evidence=affirmed_evidence,
            negated_evidence=negated_evidence,
        )
        contradictions.append(candidate)
        for source_id in all_source_ids:
            candidate_keys_by_source[source_id].add(assertion_key)

    contradictions.sort(
        key=lambda candidate: (
            -candidate.source_count,
            -candidate.evidence_count,
            candidate.subject_label.casefold(),
            candidate.predicate,
            candidate.object_label.casefold(),
            tuple(candidate.temporal_years),
        )
    )

    cross_source_ids = {
        claim.relation_id
        for claim in claims
        if claim.support_level == ClaimSupportLevel.CROSS_SOURCE
    }
    single_source_ids = {
        claim.relation_id
        for claim in claims
        if claim.support_level == ClaimSupportLevel.SINGLE_SOURCE
    }

    profiles = []
    for source_id in source_ids:
        document = source_documents.get(source_id)
        source_claim_ids = claim_ids_by_source.get(source_id, set())
        profiles.append(
            SourceClaimProfile(
                source_id=source_id,
                label=(document.filename or document.title if document is not None else source_id),
                source_type=document.source_type if document is not None else None,
                claim_count=len(source_claim_ids),
                cross_source_claim_count=len(source_claim_ids & cross_source_ids),
                single_source_claim_count=len(source_claim_ids & single_source_ids),
                contradiction_candidate_count=len(candidate_keys_by_source.get(source_id, set())),
            )
        )

    overlaps: list[SourcePairOverlap] = []
    source_relationships: list[SourceRelationshipSignal] = []
    for left_source_id, right_source_id in combinations(source_ids, 2):
        left_claims = claim_ids_by_source.get(left_source_id, set())
        right_claims = claim_ids_by_source.get(right_source_id, set())
        shared = left_claims & right_claims
        union = left_claims | right_claims
        overlaps.append(
            SourcePairOverlap(
                left_source_id=left_source_id,
                right_source_id=right_source_id,
                shared_claim_count=len(shared),
                union_claim_count=len(union),
                jaccard_similarity=(len(shared) / len(union) if union else 0.0),
                shared_relation_ids=sorted(shared),
            )
        )

        left_document = source_documents.get(left_source_id)
        right_document = source_documents.get(right_source_id)
        left_host = _origin_host(left_document)
        right_host = _origin_host(right_document)
        same_origin_host = bool(left_host and right_host and left_host == right_host)
        exact_content_match = bool(
            left_document
            and right_document
            and left_document.content_hash
            and left_document.content_hash == right_document.content_hash
        )

        exact_evidence_relation_ids: list[str] = []
        exact_evidence_text_overlap_count = 0
        for relation_id, texts_by_source in evidence_texts_by_relation_source.items():
            shared_texts = texts_by_source.get(left_source_id, set()) & texts_by_source.get(
                right_source_id, set()
            )
            if shared_texts:
                exact_evidence_relation_ids.append(relation_id)
                exact_evidence_text_overlap_count += len(shared_texts)

        possible_derivation_signal = (
            exact_content_match or exact_evidence_text_overlap_count > 0
        )
        review_reasons: list[str] = []
        if exact_content_match:
            review_reasons.append("matching persisted content fingerprint")
        if exact_evidence_text_overlap_count:
            review_reasons.append(
                "identical normalized supporting sentence on a shared resolved assertion"
            )
        if same_origin_host:
            review_reasons.append(f"same origin host: {left_host}")

        source_relationships.append(
            SourceRelationshipSignal(
                left_source_id=left_source_id,
                right_source_id=right_source_id,
                left_origin_host=left_host,
                right_origin_host=right_host,
                same_origin_host=same_origin_host,
                exact_content_fingerprint_match=exact_content_match,
                exact_evidence_text_overlap_count=exact_evidence_text_overlap_count,
                exact_evidence_relation_ids=sorted(exact_evidence_relation_ids),
                possible_derivation_signal=possible_derivation_signal,
                review_reasons=review_reasons,
            )
        )

    overlaps.sort(
        key=lambda overlap: (
            -overlap.jaccard_similarity,
            -overlap.shared_claim_count,
            overlap.left_source_id,
            overlap.right_source_id,
        )
    )
    source_relationships.sort(
        key=lambda signal: (
            not signal.possible_derivation_signal,
            not signal.exact_content_fingerprint_match,
            -signal.exact_evidence_text_overlap_count,
            not signal.same_origin_host,
            signal.left_source_id,
            signal.right_source_id,
        )
    )

    return SourceComparison(
        run_id=analysis.run.run_id,
        workspace_id=analysis.run.workspace_id,
        comparison_version=COMPARISON_VERSION,
        summary=SourceComparisonSummary(
            source_count=len(source_ids),
            claim_count=len(claims),
            cross_source_claim_count=len(cross_source_ids),
            single_source_claim_count=len(single_source_ids),
            contradiction_candidate_count=len(contradictions),
            pair_count=len(overlaps),
            exact_content_match_pair_count=sum(
                signal.exact_content_fingerprint_match for signal in source_relationships
            ),
            exact_evidence_overlap_pair_count=sum(
                signal.exact_evidence_text_overlap_count > 0
                for signal in source_relationships
            ),
            same_origin_pair_count=sum(
                signal.same_origin_host for signal in source_relationships
            ),
            possible_derivation_pair_count=sum(
                signal.possible_derivation_signal for signal in source_relationships
            ),
        ),
        sources=profiles,
        claims=claims,
        contradictions=contradictions,
        overlaps=overlaps,
        source_relationships=source_relationships,
        interpretation_note=INTERPRETATION_NOTE,
    )
