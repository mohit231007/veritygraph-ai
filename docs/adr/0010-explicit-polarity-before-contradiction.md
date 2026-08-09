# ADR 0010: Retain Explicit Assertion Polarity Before Contradiction Detection

## Status

Accepted

## Context

VerityGraph already distinguishes cross-source corroboration from single-source evidence and deliberately refuses to infer contradiction from silence. The next trust requirement is to retain incompatible source assertions without collapsing them into one positive graph relation.

A relation such as:

```text
Microsoft acquired GitHub.
```

and a relation such as:

```text
Microsoft did not acquire GitHub.
```

must not be aggregated as the same positive assertion. At the same time, the current local baseline is not a general natural-language-inference model and cannot safely resolve every form of negation, modality, temporal qualification, or semantic incompatibility.

Historical analysis runs also predate polarity retention. Reinterpreting those rows as affirmed would manufacture provenance that did not exist when they were extracted.

## Decision

VerityGraph will make polarity a first-class relation field with three values:

```text
unknown | affirmed | negated
```

For new spaCy baseline runs:

- `negated` is emitted only when the relation sentence root has an explicit dependency child with `dep_ == "neg"`;
- otherwise the extracted relation is `affirmed`;
- the normalized predicate is unchanged, so `did not acquire` remains predicate `acquire` plus polarity `negated`;
- the extractor records a polarity method string for auditability.

Relation aggregation and deterministic entity-resolution remapping include polarity in the relation identity. Affirmed and negated forms of the same resolved subject-predicate-object therefore remain separate evidence-bearing relations.

Existing SQLite rows gain the new columns through an in-place migration and receive:

```text
polarity = unknown
polarity_method = historical_unknown
```

They are not retroactively marked affirmed.

A source-comparison contradiction candidate is produced only when:

1. subject, predicate, and object are identical after entity resolution;
2. at least one retained relation is affirmed;
3. at least one retained relation is negated; and
4. at least two distinct sources are represented across the opposing evidence sets.

The candidate retains both relation sets and all original `RelationEvidence -> SourceSpan -> SourceDocument` lineage. It is explicitly not a truth verdict.

Negated relations remain visible in the evidence graph but are excluded from PageRank, centrality structure, communities, components, density, and connection paths. They must not create a positive structural link. Historical `unknown` relations remain structurally usable so old analysis runs preserve prior graph behavior while exposing their uncertain polarity.

## Consequences

### Benefits

- explicit negation can no longer silently strengthen a positive graph edge;
- contradiction candidates require evidence on both sides rather than source silence;
- historical rows remain epistemically honest;
- the implementation stays deterministic, local, explainable, and testable;
- later NLI or LLM-based contradiction adapters can be evaluated against the same persisted polarity/evidence contract.

### Limitations

- root dependency negation is intentionally narrow;
- negation scope such as nested clauses may not be classified correctly;
- lexical antonyms are not contradiction detection;
- temporal changes such as `was CEO` versus `is not CEO` are not adjudicated;
- modality and hedging are not yet represented;
- two incompatible assertions in the same source are not currently promoted to a cross-source contradiction candidate.

## Rejected alternatives

### Treat every relation without a negation token as historically affirmed

Rejected because older persisted relations were extracted before polarity existed. Rewriting their semantics would fabricate lineage.

### Encode negation into the predicate string

Rejected because `acquire` and `not acquire` should share one normalized predicate so opposing polarity can be compared directly and graph/query semantics remain composable.

### Use an LLM/NLI model immediately

Rejected for the baseline because the project does not yet have labelled contradiction evaluation, calibrated error bounds, or a reason to abandon the deterministic local trust layer. A future optional model may extend polarity and incompatibility detection only after benchmark coverage exists.

### Treat absence from another source as contradiction

Rejected because silence is not evidence of the opposite assertion.
