# Source Comparison, Corroboration, Contradiction Candidates, and Source Relationships

## Purpose

VerityGraph compares resolved qualified assertions inside one immutable `AnalysisRun` while preserving strict distinctions between corroboration, silence, modality, temporal scope, explicit incompatibility, and observable source-relationship evidence.

The comparison layer answers five transparent questions:

1. Which exact qualified assertions are supported by evidence from more than one source ID?
2. Which extracted assertions currently have evidence from only one source ID?
3. How much exact resolved-assertion overlap exists between each pair of sources?
4. Which asserted subject-predicate-object claims have opposing explicit polarity in compatible time scope across at least two sources?
5. Which source pairs expose deterministic relationship review signals such as exact content duplication, identical supporting text, or shared origin host?

It does not decide which side of a contradiction candidate is true, whether one source copied another, or whether two sources are independent.

## Exact run-source lineage

Every new `AnalysisRun` stores the ordered `source_ids` that were actually analysed. SQLite persists this membership in `analysis_run_sources`, separately from mutable current workspace membership.

Historical runs created before exact source membership was introduced keep an empty `source_ids` list rather than receiving reconstructed history that may be wrong.

## Qualified assertion identity

Comparison operates after deterministic entity resolution. A new source-derived relation is identified by:

```text
canonical subject
+ predicate
+ canonical object
+ polarity
+ modality
+ explicit year set
```

Polarity is:

```text
unknown | affirmed | negated
```

Modality is:

```text
unknown | asserted | modal
```

New local extraction marks `negated` only for explicit dependency-root negation. Direct root auxiliaries such as `may`, `might`, `could`, `will`, and `would` make an assertion `modal`. Sorted unique four-digit years visible in the sentence are retained as `temporal_years`.

Historical relations created before these fields existed are not retroactively guessed: polarity/modality remain `unknown`, and temporal method remains `historical_unknown`.

## Support levels

### Cross-source

A claim is `cross_source` only when the same resolved **qualified relation** contains evidence from at least two distinct source IDs.

```text
Source A: Microsoft acquired GitHub in 2018.
Source B: Microsoft acquired GitHub in 2018.

=> cross-source support
```

A 2018 assertion and a 2019 assertion are separate relation identities. An asserted claim and a modal claim are also separate.

Cross-source does **not** mean independently reported. Each comparison claim therefore also exposes:

- `source_count`;
- `distinct_content_fingerprint_count`;
- `distinct_evidence_text_count`.

For example:

```text
2 source IDs
1 distinct content fingerprint
1 distinct normalized evidence sentence
```

is materially different provenance context from:

```text
2 source IDs
2 distinct content fingerprints
2 distinct normalized evidence sentences
```

Neither case is converted into an independence verdict.

### Single-source

A claim is `single_source` when its retained evidence belongs to exactly one source ID. This says nothing about whether another source agrees, disagrees, or simply does not discuss it.

## Contradiction candidates

A contradiction candidate exists only when all of these conditions hold:

1. resolved subject, normalized predicate, and resolved object are identical;
2. at least one retained relation is `affirmed`;
3. at least one retained relation is `negated`;
4. both opposing sides are `asserted`, not `modal` or historical `unknown`;
5. temporal scope is compatible;
6. at least two distinct sources are represented across the opposing evidence sets.

Temporal compatibility is intentionally conservative:

- neither side has an explicit year -> compatible;
- both sides have explicit years and at least one year overlaps -> compatible;
- explicit year sets are disjoint -> not compatible;
- only one side has explicit years -> ambiguous, therefore not automatically compatible.

Example:

```text
Source A: Microsoft acquired GitHub in 2018.
Source B: Microsoft did not acquire GitHub in 2018.

=> contradiction candidate for 2018
```

But:

```text
Source A: Microsoft acquired GitHub in 2018.
Source B: Microsoft did not acquire GitHub in 2019.

=> no contradiction candidate
```

And:

```text
Source A: Microsoft may acquire GitHub in 2027.
Source B: Microsoft did not acquire GitHub in 2027.

=> no contradiction candidate because one side is modal
```

A candidate exposes both relation IDs, both source sets, compatible year scope, and every retained evidence sentence. It is an evidence-review signal, **not** a truth verdict, source-quality judgement, or calibrated probability.

## Source relationship review signals

For every pair of sources represented in the immutable run, VerityGraph produces a separate `SourceRelationshipSignal`.

The deterministic signals are:

### Exact persisted content fingerprint

If both source documents have the same persisted `content_hash`, `exact_content_fingerprint_match` is true.

This is strong evidence that the persisted source content is byte-equivalent under the ingestion contract, but it does not establish who copied whom or whether both came from a third source.

### Exact normalized supporting-text overlap

Evidence text is normalized with Unicode NFKC, case folding, and whitespace collapse. VerityGraph then looks for exact normalized evidence sentences shared by the same resolved relation across a source pair.

The projection exposes:

- `exact_evidence_text_overlap_count`;
- `exact_evidence_relation_ids`.

This is deliberately exact-match logic, not semantic similarity or paraphrase detection.

### Shared origin host

When source URLs exist, hostnames are normalized by lowercasing, stripping a leading `www.`, and removing a trailing dot.

A shared origin host is contextual evidence only. It does **not** set `possible_derivation_signal` by itself.

### Possible derivation review flag

`possible_derivation_signal` is true only when the pair has at least one of:

```text
exact content fingerprint match
OR
exact normalized supporting-text overlap on a shared resolved relation
```

The flag means **review this pair**. It does not mean one source copied another.

If no flag is present, VerityGraph says only that no deterministic derivation signal was detected. It does not claim independence.

## Critical guardrails

**Missing evidence is not contradiction.** Source silence cannot supply the opposite side of a claim.

**Different time scope is not contradiction.** Disjoint explicit years are not promoted automatically.

**Modal language is not an asserted fact.** A `may`, `might`, `could`, `will`, or similar direct modal/future assertion does not supply an asserted contradiction side.

**Historical unknown qualifiers stay unknown.** Old relations are never backfilled with guessed semantics.

**Distinct source IDs are not proof of independent reporting.** Storage identity and reporting independence are separate concepts.

**No detected source-relationship signal is not proof of independence.** Missing metadata, paraphrases, translations, and common upstream sources remain possible.

**Same origin host is not proof of derivation.** Publisher or domain context alone is insufficient.

## Source profiles

Each run source receives counts for total extracted assertions, cross-source assertions, single-source assertions, and contradiction candidates in which it contributes evidence. These are corpus-support statistics, not quality or trust ratings.

A source with no extracted relation claim remains visible for new runs because exact run-source membership is persisted separately from relation output.

## Pairwise overlap

For every source pair, VerityGraph computes exact relation-ID Jaccard similarity:

```text
J(A, B) = |claims(A) ∩ claims(B)| / |claims(A) ∪ claims(B)|
```

Because qualifier variants are separate relations, opposing polarity, different years, or different modality are not counted as ordinary shared support.

Claim overlap and source-relationship signals remain separate projections: similar claims do not automatically imply derivation.

## Evidence inspection

Selecting a comparison assertion exposes every retained evidence sentence plus its source label and source-span ID. A contradiction candidate shows affirmed and negated evidence side by side with the compatible year scope.

The source-relationship section exposes each pair's deterministic review reasons and explicitly states that a possible derivation signal is not proof of copying.

## Graph interaction

`negated` and `modal` relations remain visible in the evidence graph so their lineage can be inspected, but they are excluded from structural analytics and connection-path computation. They must not masquerade as established relationships.

Historical `unknown` qualifiers remain structurally usable so immutable older runs preserve prior graph behavior while making uncertainty explicit.

Source relationship signals currently do not change graph topology, contradiction promotion, or relation confidence. They provide provenance context for review.

## What the scores do not mean

The relation extraction-rule score is not a probability of truth. Cross-source support or contradiction status does not convert it into one.

Two sources can repeat the same incorrect statement, quote each other, or originate from the same underlying report. Exact relationship signals make some of that risk visible, but they still do not establish independence, authority, or truth.

## API

```text
GET /api/v1/analyses/{run_id}/comparison
GET /api/v1/workspaces/{workspace_id}/comparison/latest
```

The comparison is a deterministic projection and is not stored as a second mutable truth representation.

The v4 comparison response includes:

```text
claims[].distinct_content_fingerprint_count
claims[].distinct_evidence_text_count
source_relationships[]
summary.exact_content_match_pair_count
summary.exact_evidence_overlap_pair_count
summary.same_origin_pair_count
summary.possible_derivation_pair_count
```

## Next trust-layer improvements

1. preserve explicit citation/reference lineage from source documents and web pages;
2. richer temporal expressions such as ranges, relative dates, and `currently`;
3. reported speech, conditionals, and hedging such as `allegedly`;
4. publisher/organization ownership metadata without hard-coded trust rankings;
5. paraphrase/republication detection only after a labelled evaluation set exists;
6. human adjudication of contradiction and derivation review candidates;
7. calibrated claim-level confidence only after labelled evaluation.
