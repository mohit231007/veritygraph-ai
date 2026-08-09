# ADR 0012: Treat Source Relationship Evidence as Review Signals, Not Independence Proof

## Status

Accepted

## Context

Cross-source support currently means that the same resolved qualified assertion retains evidence from at least two distinct source IDs. That is useful, but source identifiers are storage identities, not proof of independent reporting.

Two source records can represent the same underlying material, repeat an identical supporting sentence, or originate from the same host. Conversely, two sources with no detected relationship signal are not automatically independent.

A trust-oriented system must expose what it can actually observe without converting sparse provenance clues into unsupported causal claims such as "source B copied source A" or fabricated independence scores.

## Decision

The source-comparison projection adds deterministic, inspectable relationship signals while leaving corroboration and contradiction semantics unchanged.

For every cross-source claim, VerityGraph records:

- the number of distinct source IDs;
- the number of distinct persisted content fingerprints represented by those sources;
- the number of distinct normalized evidence sentences retained for the claim.

For every source pair in the immutable analysis run, VerityGraph records a `SourceRelationshipSignal` containing:

- normalized origin hosts when URLs are available;
- whether both sources have the same persisted content fingerprint;
- how many identical normalized supporting sentences occur on the same resolved relation;
- the relation IDs on which exact evidence text overlaps;
- transparent human-readable review reasons;
- a conservative `possible_derivation_signal`.

The possible-derivation flag is true only when either:

1. persisted content fingerprints match exactly; or
2. identical normalized supporting text is retained for the same resolved relation across the pair.

A shared origin host is retained as context but is **not sufficient** by itself to set `possible_derivation_signal`.

## Non-claims

These signals must never be presented as proof that:

- one source copied another;
- two sources share a common upstream source;
- two sources are independent;
- a publisher is authoritative or untrustworthy;
- corroborated content is true.

Absence of a detected relationship signal is not evidence of independence.

## Normalization

Evidence text comparison uses deterministic Unicode NFKC normalization, case folding, whitespace collapse, and exact equality after normalization. It is intentionally not semantic similarity or paraphrase detection.

Origin host comparison lowercases hostnames, removes a leading `www.`, and strips a trailing dot. It does not infer publisher ownership across different domains.

Persisted `content_hash` remains the canonical exact-content fingerprint.

## Interaction with corroboration

`cross_source` retains its narrow meaning: evidence for one exact qualified assertion comes from at least two distinct source IDs.

The UI must show source count beside content/evidence diversity so users can distinguish cases such as:

```text
2 source IDs
1 distinct content fingerprint
1 distinct supporting sentence
```

from:

```text
2 source IDs
2 distinct content fingerprints
2 distinct supporting sentences
```

Neither case receives an independence verdict.

## Interaction with contradiction candidates

Source relationship signals do not currently suppress, promote, or adjudicate contradiction candidates. The contradiction rule remains:

```text
same resolved subject/predicate/object
+ opposing explicit polarity
+ asserted on both sides
+ compatible explicit time scope
+ at least two distinct source IDs across both sides
```

The relationship projection gives a reviewer additional provenance context without silently rewriting the contradiction contract.

## Consequences

### Benefits

- duplicate material can no longer masquerade as obviously diverse evidence in the UI;
- exact repeated supporting text becomes reviewable without an LLM;
- same-host context is visible without overclaiming derivation;
- all signals are deterministic, local-first, auditable, and cheap to recompute;
- future citation-chain and ownership metadata can extend the same projection.

### Limitations

- exact text overlap misses paraphrases and translated reuse;
- hostname equality is not publisher-ownership resolution;
- different content fingerprints do not imply independence;
- identical sentences can arise independently, especially for short factual statements;
- no direction of derivation is inferred;
- citation/reference lineage is not yet preserved.

## Rejected alternatives

### Assign an independence score

Rejected because there is no labelled evaluation or sufficient provenance evidence to calibrate such a score.

### Treat same hostname as derivation

Rejected because two genuinely independent articles can share one publisher host.

### Treat no detected signal as independent

Rejected because missing metadata and paraphrased reuse would make that conclusion unsafe.

### Use semantic similarity immediately

Rejected for this baseline because similarity would introduce threshold calibration and false-positive risk before exact deterministic signals have been benchmarked.
