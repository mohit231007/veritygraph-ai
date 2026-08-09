# ADR 0011: Retain Conservative Modality and Temporal Qualifiers

## Status

Accepted

## Context

Assertion polarity prevents an explicitly negated sentence from being collapsed into a positive relation, but polarity alone is not enough for trustworthy contradiction detection or graph inference.

These statements do not have equivalent factual scope:

```text
Microsoft acquired GitHub in 2018.
Microsoft did not acquire GitHub in 2019.
Microsoft may acquire GitHub in 2027.
```

Treating the first two as a direct contradiction ignores time. Treating the third as an established graph relationship ignores modality. A trust-oriented baseline should prefer missing a candidate over manufacturing one when scope is ambiguous.

The project is still intentionally local-first and deterministic. We do not yet have labelled evaluation sufficient to justify a general temporal-reasoning, factuality, or natural-language-inference model.

## Decision

Every new `Relation` records two additional qualifier dimensions.

### Modality

```text
unknown | asserted | modal
```

The local spaCy baseline emits `modal` only when the relation root has a direct auxiliary whose normalized form is one of:

```text
can, could, may, might, must, shall, should, will, would
```

Otherwise a new extraction is `asserted`. Historical relations created before this field existed migrate to `unknown` rather than being retroactively guessed.

### Explicit year scope

A relation retains sorted unique four-digit years found in its evidence sentence using a conservative deterministic year pattern. This is deliberately not a full temporal parser. Historical rows migrate with an empty year list and `historical_unknown` temporal method.

Relation aggregation identity includes:

```text
subject
predicate
object
polarity
modality
explicit year set
```

so different qualifier scopes cannot silently merge their evidence.

## Contradiction rule

A contradiction candidate now requires all of the following:

1. identical resolved subject, predicate, and object;
2. at least one `affirmed` relation and at least one `negated` relation;
3. both sides have modality `asserted`;
4. temporal scope is compatible;
5. at least two distinct sources are represented across the opposing evidence.

Temporal compatibility is intentionally strict:

- both sides have no explicit year -> compatible;
- both sides have explicit years with at least one overlapping year -> compatible;
- disjoint explicit year sets -> incompatible;
- one side has explicit years and the other has none -> ambiguous, therefore incompatible for automatic contradiction promotion.

This rule is designed to reduce false positives, not maximize recall.

## Graph rule

`negated` and `modal` relations remain visible as evidence-bearing graph edges but do not contribute to structural graph analytics or connection paths.

Historical `unknown` qualifiers remain structurally usable to preserve the behavior of older immutable analysis runs while making the uncertainty explicit.

## Consequences

### Benefits

- future/modal statements cannot inflate PageRank or create factual connection paths;
- obvious cross-year false contradiction candidates are blocked;
- one-sided temporal ambiguity fails closed;
- source evidence and qualifiers remain explainable and auditable;
- future temporal/NLI adapters can extend the same persisted contract rather than replacing it.

### Limitations

- four-digit year extraction is not full temporal normalization;
- relative expressions such as `last year`, `next quarter`, and `currently` are not resolved;
- date ranges are represented only as the years visible in the sentence;
- modality scope in nested clauses is not solved;
- reported speech, hedging such as `allegedly`, and conditional language are not yet modelled;
- `must` can express obligation or inference, which this baseline conservatively groups under modal.

## Rejected alternatives

### Treat any opposing polarity as contradiction

Rejected because it creates obvious false positives across time and uncertainty.

### Treat one explicit year and one unscoped assertion as compatible

Rejected because the unscoped statement may refer to a different period. The baseline fails closed until stronger temporal reasoning exists.

### Let modal relations participate in graph centrality

Rejected because `may acquire` or `will acquire` is not the same evidential relationship as `acquired`.

### Add a general LLM/NLI temporal reasoner immediately

Rejected until there is a labelled evaluation set and explicit error budget. The deterministic qualifier layer provides a safer benchmarkable foundation first.
