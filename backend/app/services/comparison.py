from __future__ import annotations

from collections import defaultdict
from itertools import combinations

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
)
from app.domain.source import SourceDocument

COMPARISON_VERSION = "source-corroboration-v3-qualifiers"
INTERPRETATION_NOTE = (
    "Cross-source means the same resolved assertion, polarity, modality, and explicit year "
    "scope has retained evidence from at least two distinct sources in this analysis run. "
    "A contradiction candidate requires asserted (not modal) affirmed and explicitly negated "
    "evidence for the same resolved subject-predicate-object with compatible explicit time "
    "scope and at least two distinct sources across the two sides. Unknown historical "
    "qualifiers, one-sided time scope, disjoint years, modal language, and source silence are "
    "never treated as contradictions. A candidate identifies incompatible retained evidence; "
    "it does not determine which side is true."
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


def build_source_comparison(
    analysis: WorkspaceAnalysis,
    *,
    source_documents: dict[str, SourceDocument],
) -> SourceComparison:
    """Compare exact qualified support without inferring contradiction from silence."""

    entity_names = {entity.entity_id: entity.canonical_name for entity in analysis.entities}
    source_ids = _source_ids_for_run(analysis)
    source_order = {source_id: index for index, source_id in enumerate(source_ids)}

    claims: list[ComparisonClaim] = []
    claim_ids_by_source = {source_id: set() for source_id in source_ids}
    relations_by_assertion: dict[tuple[str, str, str], list[Relation]] = defaultdict(list)

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
            evidence_count=len(relation.evidence),
            evidence=relation.evidence,
        )
        claims.append(claim)
        for source_id in evidence_source_ids:
            claim_ids_by_source.setdefault(source_id, set()).add(relation.relation_id)

    claims.sort(
        key=lambda claim: (
            claim.support_level != ClaimSupportLevel.CROSS_SOURCE,
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

    overlaps = []
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
    overlaps.sort(
        key=lambda overlap: (
            -overlap.jaccard_similarity,
            -overlap.shared_claim_count,
            overlap.left_source_id,
            overlap.right_source_id,
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
        ),
        sources=profiles,
        claims=claims,
        contradictions=contradictions,
        overlaps=overlaps,
        interpretation_note=INTERPRETATION_NOTE,
    )
