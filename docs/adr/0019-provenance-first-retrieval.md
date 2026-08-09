# ADR 0019: Rank Persisted Evidence Before Graph Expansion or LLM Synthesis

## Status

Accepted

## Context

VerityGraph now has two trustworthy local topology layers:

1. an evidence graph projected from extracted relations and exact source spans; and
2. an explicit citation graph admitted only from uniquely resolved provenance.

The next product step is retrieval. Jumping directly from those graphs to LLM synthesis would hide an important boundary: a source can be connected by citation without containing evidence relevant to the user's query.

For example, if source A contains a lexical match and explicitly cites source B, the citation edge makes B useful discovery context. It does not make B's content relevant evidence for the query without separately retrieving and scoring B's spans.

VerityGraph therefore needs a deterministic retrieval preview before adding embeddings, semantic reranking, graph expansion into evidence, or answer generation.

## Decision

VerityGraph exposes:

```text
POST /api/v1/workspaces/{workspace_id}/retrieval/preview
```

with request:

```text
query
limit
```

The response has two intentionally separate collections:

```text
hits
citation_context
```

### Direct evidence hits

`hits` contains only persisted `SourceSpan` records that directly match the lexical query.

The baseline uses local BM25 scoring over all spans in the current workspace. It does not use source-level citation degree, PageRank, source type, extraction score, or citation connectivity to alter the lexical score.

Each hit retains:

```text
rank
source_id
source_label
span_id
text
page_number?
section?
paragraph_number?
char_start
char_end
score
matched_terms
```

The score is a ranking value within this retrieval request. It is not a probability, factual-confidence score, source-quality score, or truth score.

## BM25 baseline

The implementation uses a deterministic BM25-style local score with:

```text
k1 = 1.5
b  = 0.75
```

IDF is calculated from the current workspace's persisted spans for the unique lexical query terms.

Tokenization is intentionally simple and deterministic for this first baseline: ASCII alphanumeric terms may retain internal `.`, `_`, `/`, and `-` separators. Query terms are lowercased and de-duplicated while preserving their first-seen order.

No global corpus statistics are fetched or persisted.

## Citation discovery context

After direct hits are selected, VerityGraph projects one-hop incoming/outgoing citation edges for the sources containing those hits.

Those records are returned only under:

```text
citation_context
```

Each context item contains:

```text
edge_id
seed_source_id
seed_source_label
direction
neighbor_source_id
neighbor_label
mechanisms
evidence_count
```

Citation context does **not**:

- change BM25 scores;
- change hit ranks;
- insert the neighbor's spans into `hits`;
- assert that the neighbor supports the query;
- assert that the citation is positive or endorsing;
- become answer evidence automatically.

If no span directly matches the query, graph connectivity does not create retrieval results and `citation_context` remains empty.

## Why graph expansion is separate

A citation edge is provenance, not semantic relevance.

The safe retrieval sequence is therefore:

```text
query
  -> retrieve exact persisted spans
  -> identify directly matched source IDs
  -> attach citation neighbors as discovery context
```

not:

```text
query
  -> find any connected source
  -> assume its content is relevant evidence
```

Future graph expansion may retrieve and independently score neighbor spans, but that must be an explicit evaluated stage with its own provenance and ranking signal.

## No synthesis in Phase 18

This endpoint generates no answer, summary, recommendation, or claim.

It does not call:

- an LLM;
- an embedding model;
- a reranker;
- a web search engine;
- DOI/arXiv/ISBN registries;
- external vector databases.

The preview is meant to make the future GraphRAG evidence set inspectable before synthesis exists.

## Persistence

Retrieval previews are not persisted as truth records.

They are regenerated from:

```text
WorkspaceDetail
SourceBundle / SourceSpan
explicit citation graph
```

The underlying sources and provenance remain the persistent records.

## User-interface contract

The browser renders separate sections:

```text
Ranked evidence spans
Citation discovery context — not ranked evidence
```

and displays the guardrail:

```text
Citation neighbor ≠ retrieved evidence or query support.
```

A user can therefore inspect why a span was directly retrieved and separately see where its source sits in explicit citation topology.

## Non-claims

A high BM25 score does not prove:

- factual correctness;
- semantic completeness;
- source authority;
- claim support;
- truth.

A citation-context neighbor does not prove:

- query relevance;
- endorsement;
- factual support;
- agreement;
- source dependence;
- authority;
- truth.

No result should be interpreted beyond its observable retrieval/provenance signal.

## Rejected alternatives

### Boost lexical ranking using citation in-degree

Rejected because citation degree is not query relevance or authority, and would mix two distinct signals before evaluation.

### Automatically append all citation-neighbor spans

Rejected because connectivity alone is insufficient evidence of relevance.

### Add embeddings immediately

Rejected for this phase because the deterministic lexical baseline gives us an auditable reference point against which semantic retrieval can later be evaluated.

### Generate an LLM answer from the top hits immediately

Rejected because retrieval quality and provenance need to be inspectable and tested before synthesis obscures failure modes.

## Consequences

### Benefits

- every ranked result remains an exact persisted span;
- retrieval can be tested independently from generation;
- citation topology adds useful discovery context without contaminating evidence ranking;
- empty lexical retrieval fails closed instead of graph-expanding opportunistically;
- the browser exposes exact span location, matched terms, score, and citation context;
- future GraphRAG has a deterministic baseline for evaluation.

### Limitations

- lexical retrieval misses synonyms and paraphrases;
- the initial tokenizer is English/ASCII-oriented;
- BM25 statistics are workspace-relative;
- citation-neighbor content is not semantically scored in this phase;
- no query history or retrieval result is persisted;
- no relevance labels or benchmark metrics are included yet.

## Next extensions

1. build a small labelled retrieval-evaluation corpus and report Recall@K / MRR;
2. add optional local semantic retrieval as a separately scored candidate channel;
3. evaluate deterministic fusion such as reciprocal-rank fusion rather than silently replacing BM25;
4. optionally retrieve citation-neighbor spans and score them independently;
5. construct an inspectable evidence pack for grounded synthesis;
6. add LLM answer generation only when every answer citation can resolve back to exact `SourceSpan` evidence.
