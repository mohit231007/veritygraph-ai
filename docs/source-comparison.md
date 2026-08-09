# Source Comparison and Corroboration

## Purpose

VerityGraph compares the resolved relation claims inside one immutable `AnalysisRun` without treating silence as disagreement.

The first comparison release answers three transparent questions:

1. Which extracted claims are supported by evidence from more than one source?
2. Which extracted claims currently have evidence from only one source?
3. How much exact resolved-claim overlap exists between each pair of sources?

It does **not** yet infer semantic contradiction.

## Exact run-source lineage

Every new `AnalysisRun` stores the ordered `source_ids` that were actually analysed. SQLite persists this membership in `analysis_run_sources`.

This is deliberately separate from current workspace membership. A user can later remove or add a workspace source without changing which sources belonged to an older analysis run.

Historical runs created before exact source membership was introduced keep an empty `source_ids` list rather than receiving reconstructed history that may be wrong. Comparison can still discover claim-bearing source IDs from retained entity mentions and relation evidence, but it does not pretend that this reconstructs sources that produced no extracted claims.

## Claim identity

Comparison operates after deterministic entity resolution. A claim is therefore the persisted canonical relation:

```text
canonical subject -> predicate -> canonical object
```

The persisted `relation_id` remains the comparison claim identifier, and every evidence sentence retains its original source ID and source-span ID.

## Support levels

### Cross-source

A claim is `cross_source` when the same persisted resolved relation contains evidence from at least two distinct source IDs.

Example:

```text
Source A: Microsoft acquired GitHub.
Source B: Microsoft acquired GitHub.

=> Microsoft --acquire--> GitHub
   support_level = cross_source
   source_count = 2
```

### Single-source

A claim is `single_source` when its retained evidence belongs to exactly one source ID.

This means only that VerityGraph currently has one source supporting that extracted relation in the run.

## Critical guardrail: missing evidence is not contradiction

If Source A contains `Microsoft acquired GitHub` and Source B does not contain that claim, VerityGraph labels the claim single-source with respect to the available extracted evidence. It does **not** say that Source B contradicts Source A.

Contradiction requires positive evidence of an incompatible assertion, not the absence of matching text. Explicit polarity/negation and contradiction semantics therefore belong to a later independently tested release.

## Source profiles

Each run source receives a profile containing:

- total extracted resolved claims in that source;
- number of those claims corroborated by another run source;
- number currently supported only by that source.

A source with no extracted relation claim is still retained in new analysis-run membership and therefore appears with zero counts.

These are corpus-support statistics, not quality or trust ratings.

## Pairwise overlap

For every source pair, VerityGraph computes exact-claim Jaccard similarity:

```text
J(A, B) = |claims(A) ∩ claims(B)| / |claims(A) ∪ claims(B)|
```

The API also exposes:

- shared claim count;
- union claim count;
- the exact shared `relation_id` values.

If both sources have zero extracted claims, similarity is reported as `0.0` rather than implying meaningful agreement from an empty comparison.

## Evidence inspection

Selecting a comparison claim exposes every retained evidence sentence plus its source label and source-span ID. Cross-source support is therefore inspectable rather than represented only as an aggregate count.

## What the score does not mean

The relation's extraction-rule score remains an extraction signal. Cross-source support does not convert it into a probability of truth.

Two sources can repeat the same incorrect statement, quote each other, or originate from the same underlying report. Source independence, authority, recency, contradiction, and calibrated claim confidence are separate dimensions for later evaluation.

## API

```text
GET /api/v1/analyses/{run_id}/comparison
GET /api/v1/workspaces/{workspace_id}/comparison/latest
```

The comparison is a deterministic projection and is not stored as a second mutable truth representation.

## Next trust-layer improvements

1. explicit negation/polarity retention during relation extraction;
2. contradiction candidates only when incompatible assertions are both evidenced;
3. source independence and citation-chain signals;
4. configurable source trust metadata without hard-coded publisher rankings;
5. temporal claim comparison;
6. side-by-side evidence review and human adjudication;
7. calibrated claim-level confidence only after labelled evaluation.
