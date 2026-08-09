from __future__ import annotations

from itertools import combinations

from app.domain.analysis import WorkspaceAnalysis
from app.domain.comparison import (
    ClaimSupportLevel,
    ComparisonClaim,
    SourceClaimProfile,
    SourceComparison,
    SourceComparisonSummary,
    SourcePairOverlap,
)
from app.domain.source import SourceDocument

COMPARISON_VERSION = "source-corroboration-v1"
INTERPRETATION_NOTE = (
    "Cross-source means the same resolved subject-predicate-object relation has retained "
    "evidence from at least two distinct sources in this analysis run. A claim appearing "
    "in only one source is single-source evidence. Absence from another source is not a "
    "contradiction."
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


def build_source_comparison(
    analysis: WorkspaceAnalysis,
    *,
    source_documents: dict[str, SourceDocument],
) -> SourceComparison:
    """Compare relation support without inferring disagreement from missing evidence."""

    entity_names = {
        entity.entity_id: entity.canonical_name
        for entity in analysis.entities
    }
    source_ids = _source_ids_for_run(analysis)
    source_order = {source_id: index for index, source_id in enumerate(source_ids)}

    claims: list[ComparisonClaim] = []
    claim_ids_by_source = {source_id: set() for source_id in source_ids}

    for relation in analysis.relations:
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
            subject_label=entity_names.get(
                relation.subject_entity_id,
                relation.subject_entity_id,
            ),
            predicate=relation.predicate,
            object_entity_id=relation.object_entity_id,
            object_label=entity_names.get(
                relation.object_entity_id,
                relation.object_entity_id,
            ),
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
                label=(
                    document.filename or document.title
                    if document is not None
                    else source_id
                ),
                source_type=document.source_type if document is not None else None,
                claim_count=len(source_claim_ids),
                cross_source_claim_count=len(source_claim_ids & cross_source_ids),
                single_source_claim_count=len(source_claim_ids & single_source_ids),
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

    cross_source_claim_count = len(cross_source_ids)
    single_source_claim_count = len(single_source_ids)
    return SourceComparison(
        run_id=analysis.run.run_id,
        workspace_id=analysis.run.workspace_id,
        comparison_version=COMPARISON_VERSION,
        summary=SourceComparisonSummary(
            source_count=len(source_ids),
            claim_count=len(claims),
            cross_source_claim_count=cross_source_claim_count,
            single_source_claim_count=single_source_claim_count,
            pair_count=len(overlaps),
        ),
        sources=profiles,
        claims=claims,
        overlaps=overlaps,
        interpretation_note=INTERPRETATION_NOTE,
    )
