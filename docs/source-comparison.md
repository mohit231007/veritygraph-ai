# Source Comparison, Corroboration, and Contradiction Candidates

## Purpose

VerityGraph compares resolved assertions inside one immutable `AnalysisRun` while preserving a strict distinction between corroboration, silence, and explicit incompatibility.

The comparison layer answers four transparent questions:

1. Which extracted assertions with the same polarity are supported by evidence from more than one source?
2. Which extracted assertions currently have evidence from only one source?
3. How much exact resolved-assertion overlap exists between each pair of sources?
4. Which resolved subject-predicate-object assertions have both affirmed and explicitly negated evidence across at least two sources?

It does not decide which side of a contradiction candidate is true.

## Exact run-source lineage

Every new `AnalysisRun` stores the ordered `source_ids` that were actually analysed. SQLite persists this membership in `analysis_run_sources`.

This is deliberately separate from current workspace membership. A user can later remove or add a workspace source without changing which sources belonged to an older analysis run.

Historical runs created before exact source membership was introduced keep an empty `source_ids` list rather than receiving reconstructed history that may be wrong. Comparison can still discover claim-bearing source IDs from retained entity mentions and relation evidence, but it does not pretend that this reconstructs sources that produced no extracted claims.

## Assertion identity

Comparison operates after deterministic entity resolution. A source-derived assertion is represented as:

```text
canonical subject -> predicate -> canonical object -> polarity
```

Polarity is one of:

- `affirmed`
- `negated`
- `unknown`

New local extraction classifies `negated` only when spaCy exposes explicit dependency-root negation. New assertions without that explicit negation are `affirmed`. Historical relations created before polarity existed migrate to `unknown` rather than being retroactively guessed.

The persisted `relation_id` remains the identity of one polarity-specific relation, and every evidence sentence retains its original source ID and source-span ID.

## Support levels

### Cross-source

A claim is `cross_source` when the same resolved relation **and polarity** contains evidence from at least two distinct source IDs.

Example:

```text
Source A: Microsoft acquired GitHub.
Source B: Microsoft acquired GitHub.

=> Microsoft --acquire / affirmed--> GitHub
   support_level = cross_source
   source_count = 2
```

### Single-source

A claim is `single_source` when its retained evidence belongs to exactly one source ID.

This means only that VerityGraph currently has one source supporting that extracted polarity-specific assertion in the run.

## Contradiction candidates

A contradiction candidate exists only when all of these conditions hold:

1. the resolved subject is identical;
2. the normalized predicate is identical;
3. the resolved object is identical;
4. at least one retained relation is `affirmed`;
5. at least one retained relation is `negated`;
6. at least two distinct sources are represented across the opposing evidence sets.

Example:

```text
Source A: Microsoft acquired GitHub.
Source B: Microsoft did not acquire GitHub.

=> assertion key: Microsoft | acquire | GitHub
   affirmed evidence: Source A
   negated evidence:  Source B
   result: contradiction candidate
```

The candidate exposes both relation IDs, both source sets, and every retained evidence sentence. It is an evidence-review signal, **not** a truth verdict, source-quality judgement, or calibrated probability.

A positive and negated sentence inside only one source do not currently become a cross-source contradiction candidate. They remain separately inspectable assertions and can support a later within-document consistency feature.

## Critical guardrail: missing evidence is not contradiction

If Source A contains `Microsoft acquired GitHub` and Source B does not contain that claim, VerityGraph labels the assertion single-source with respect to the available extracted evidence. It does **not** say that Source B contradicts Source A.

Likewise, historical `unknown` polarity never supplies either side of a contradiction candidate.

Contradiction requires retained incompatible positive evidence, not the absence of matching text.

## Source profiles

Each run source receives a profile containing:

- total extracted resolved assertions in that source;
- number corroborated by another run source with the same polarity;
- number currently supported only by that source;
- number of contradiction candidates in which the source contributes evidence.

A source with no extracted relation assertion is still retained in new analysis-run membership and therefore appears with zero counts.

These are corpus-support statistics, not quality or trust ratings.

## Pairwise overlap

For every source pair, VerityGraph computes exact relation-ID Jaccard similarity:

```text
J(A, B) = |claims(A) ∩ claims(B)| / |claims(A) ∪ claims(B)|
```

Because affirmed and negated assertions are persisted as distinct relations, opposing polarity is not counted as ordinary shared support.

The API also exposes:

- shared claim count;
- union claim count;
- the exact shared `relation_id` values.

If both sources have zero extracted claims, similarity is reported as `0.0` rather than implying meaningful agreement from an empty comparison.

## Evidence inspection

Selecting a comparison assertion exposes every retained evidence sentence plus its source label and source-span ID. A contradiction candidate shows affirmed and negated evidence side by side.

## Graph interaction

Negated relations remain visible in the evidence graph so their lineage can be inspected. They are excluded from the structural analytics projection and from connection-path computation because a negated assertion must not masquerade as a positive relationship.

Historical `unknown` relations remain in the structural projection to preserve old-run behavior while making their uncertain polarity explicit.

## What the scores do not mean

The relation's extraction-rule score remains an extraction signal. Cross-source support or contradiction status does not convert it into a probability of truth.

Two sources can repeat the same incorrect statement, quote each other, or originate from the same underlying report. Source independence, authority, recency, temporal scope, contradiction adjudication, and calibrated claim confidence are separate dimensions for later evaluation.

## API

```text
GET /api/v1/analyses/{run_id}/comparison
GET /api/v1/workspaces/{workspace_id}/comparison/latest
```

The comparison is a deterministic projection and is not stored as a second mutable truth representation.

## Next trust-layer improvements

1. scope-aware negation beyond direct root negation, with labelled evaluation;
2. temporal qualifiers so facts from different dates are not falsely treated as contradictions;
3. modality/hedging such as `may`, `plans to`, and `allegedly`;
4. source independence and citation-chain signals;
5. configurable source trust metadata without hard-coded publisher rankings;
6. side-by-side human adjudication of contradiction candidates;
7. calibrated claim-level confidence only after labelled evaluation.
