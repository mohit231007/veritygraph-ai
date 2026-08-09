# ADR 0021: Grounded evidence pack before generation

## Status

Accepted.

## Context

VerityGraph now has persisted `SourceSpan` provenance, explicit reference/identifier lineage, deterministic citation topology, BM25 span retrieval and labelled retrieval evaluation. The next unsafe shortcut would be to pass a loosely assembled mixture of direct hits and graph neighbors to a generator.

A citation edge proves only that explicit provenance uniquely resolved one workspace source to another. It does not prove that the neighbor supports the user's query. Therefore citation-neighbor text must not enter generator context merely because a graph edge exists.

## Decision

Introduce a deterministic `GroundedEvidencePack` between retrieval and any future answer generator.

The pack is built only from spans returned by the production lexical ranker.

```text
query
  -> production BM25 ranker
  -> direct SourceSpan hits
  -> rank-preserving budget policy
  -> exact excerpt windows
  -> GroundedEvidencePack
```

Citation topology is attached separately:

```text
selected direct-evidence source
  -> uniquely resolved citation edge
  -> metadata-only discovery context
```

Citation context never contributes text to `EvidenceExcerpt` unless a span from that neighbor independently matches the query and is selected by the same direct retrieval process.

## Budget policy

The request exposes explicit limits:

- maximum excerpt count;
- maximum excerpts per source;
- maximum characters per excerpt;
- maximum total excerpt characters.

Selection remains in retrieval-rank order. The per-source cap can skip a later hit from an already represented source so lower-ranked direct hits from other sources can still enter the bounded pack. This is a transparent diversity constraint, not a semantic reranker.

## Exact excerpt provenance

Every excerpt retains:

```text
source_id
source_label
span_id
span_char_start / span_char_end
excerpt_char_start / excerpt_char_end
page / section / paragraph locators when available
retrieval rank
BM25 score
matched lexical terms
truncation flags
```

If a span is longer than the per-excerpt budget, the deterministic window is anchored around the earliest matched query term. The excerpt is an exact substring of the normalized persisted span; absolute normalized-corpus offsets are retained.

## Non-claims

A selected excerpt does not prove:

- factual correctness;
- source authority;
- source independence;
- relevance beyond the lexical scoring rule;
- sufficient evidence for an answer;
- truth.

BM25 score is a ranking signal, not calibrated confidence.

Citation context does not prove support, agreement, endorsement, dependence, copying, authority or truth.

## Generator contract

A future generator may consume the evidence block produced from `GroundedEvidencePack`, but must not silently add citation-neighbor text or untracked source text. Generated claims should later map back to the excerpt IDs/ranges they relied on.

## Consequences

### Positive

- generator context becomes inspectable before generation;
- prompt budgets are deterministic and user-controlled;
- direct evidence and graph discovery remain semantically separate;
- future answer evaluation can identify exactly what evidence was available;
- copy/download workflows can export the packet without invoking a model.

### Trade-offs

- lexical retrieval can miss semantically relevant spans;
- character budgets can truncate useful surrounding context;
- rank-preserving selection is simpler but less flexible than learned reranking;
- per-source diversity is a policy choice and not evidence of source independence.

Those trade-offs are deliberate and measurable. Semantic retrieval/reranking should be compared against the existing labelled retrieval evaluation rather than replacing this baseline without evidence.
