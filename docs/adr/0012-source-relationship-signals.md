# ADR 0012: Treat Source Relationship Evidence as Review Signals, Not Independence Proof

## Status

Proposed

## Context

VerityGraph can now identify cross-source support using distinct source IDs. That is useful, but distinct source IDs are not equivalent to independent reporting.

Two source records may represent:

- the same document uploaded twice under different filenames;
- two pages from the same publisher or origin host;
- two pages that repeat the exact same supporting sentence;
- genuinely independent reports that happen to use identical wording;
- derivative reporting where one source quotes or republishes another;
- separate sources that ultimately rely on one common upstream source.

The current product does not retain enough citation-chain or publication-history evidence to prove source independence or copying. It should therefore surface transparent relationship evidence without converting it into a binary trust judgement.

## Decision

Source comparison will retain the existing meaning of `cross_source`: the same qualified relation has evidence from at least two distinct source IDs.

It will additionally expose conservative source-pair review signals derived only from persisted local evidence:

1. **Matching persisted content fingerprint** — both source records have the same stored content hash.
2. **Identical normalized supporting sentence** — the same normalized evidence sentence supports the same resolved relation in both sources.
3. **Same origin host** — both URL-backed sources resolve to the same normalized hostname.

The first two create a `possible_derivation_signal` because they are strong enough to warrant review. Same-origin host is reported separately as context and does not by itself create that flag.

For each cross-source claim, VerityGraph also reports:

- raw distinct source-ID count;
- distinct persisted content-fingerprint count;
- distinct normalized evidence-text count.

This allows the UI to show cases such as:

```text
2 source IDs
1 distinct content fingerprint
1 distinct supporting sentence
```

without claiming that either source copied the other.

## Non-claims

A relationship signal does **not** prove:

- plagiarism;
- republication;
- common ownership;
- citation dependence;
- source independence;
- factual correctness.

Likewise, absence of these signals does not prove independence. Two independently written sources may use identical wording, and two derivative sources may paraphrase enough to avoid exact-match signals.

## Consequences

### Benefits

- cross-source support no longer visually implies independence;
- duplicate uploads can be recognized as weaker diversity than two different content fingerprints;
- exact repeated support text becomes inspectable evidence rather than hidden duplication;
- same-domain reporting can be surfaced without hard-coded publisher trust rankings;
- the implementation remains deterministic, local, explainable, and free of external APIs.

### Limitations

- content fingerprints depend on the canonical persisted content representation used by ingestion;
- exact evidence-text matching misses paraphrased derivation;
- same hostname does not imply editorial dependence;
- no citation graph, author identity, publication timestamp, or syndication metadata is yet used;
- source ownership and corporate relationships are not inferred.

## Future extensions

1. explicit citation/reference extraction;
2. canonical URL and redirect lineage;
3. publication timestamps and update history;
4. local near-duplicate sentence/document fingerprints with labelled thresholds;
5. source ownership metadata supplied by users or trusted public registries;
6. citation-chain graph analytics;
7. calibrated support-diversity metrics only after evaluation.
