# ADR 0020: Evaluate Retrieval Against Explicit Span-Level Relevance Labels

## Status

Accepted

## Context

VerityGraph now has a deterministic provenance-first retrieval baseline. Direct `SourceSpan` evidence is ranked lexically with BM25, while citation neighbors are returned separately as discovery context.

Before adding semantic embeddings, rerankers, graph expansion, or LLM synthesis, the baseline needs measurable retrieval quality. Otherwise later changes could be described as improvements without a reproducible benchmark.

The evaluation layer must score the exact production ranker, not a parallel implementation, and stale labels must fail loudly rather than silently degrading metrics.

## Decision

VerityGraph exposes:

```text
POST /api/v1/workspaces/{workspace_id}/retrieval/evaluate
```

The request contains explicit labelled cases:

```text
case_id
query
relevant_span_ids
```

plus one or more requested K values between 1 and 25.

Each `relevant_span_id` must exist in the current workspace. Unknown span IDs cause a 422 response. Duplicate `case_id` values also fail closed.

## Production-ranker reuse

Phase 18's lexical logic is factored into one production function:

```text
rank_workspace_spans(...)
```

Both the interactive retrieval preview and the evaluation service call that same ranker.

Evaluation does not maintain its own tokenization, BM25 implementation, tie-breaking rule, or score calculation.

This prevents the benchmark from measuring code that differs from what users actually run.

## Metrics

The baseline reports:

```text
Recall@K
Precision@K
HitRate@K
Mean Reciprocal Rank (MRR)
```

### Recall@K

For each case:

```text
number of labelled relevant spans in top K
------------------------------------------
number of labelled relevant spans
```

Aggregate Recall@K is the arithmetic mean across evaluation cases.

### Precision@K

For each case:

```text
number of labelled relevant spans in top K
------------------------------------------
K
```

K remains the denominator even when fewer than K spans receive a positive lexical score. Missing positions therefore do not become free precision.

### HitRate@K

A case contributes 1 when at least one labelled relevant span appears in the first K ranks and 0 otherwise. The aggregate is the mean across cases.

### Mean Reciprocal Rank

For each case, the ranker is evaluated across the full set of lexically matched workspace spans. The reciprocal rank is:

```text
1 / rank of first labelled relevant span
```

If no labelled relevant span receives a lexical match, the case contributes 0.

MRR is the arithmetic mean of those reciprocal ranks.

## Per-case diagnostics

Each case returns:

```text
relevant_span_ids
retrieved_span_ids       # up to the largest requested K
first_relevant_rank
reciprocal_rank
metrics_at_k
```

This makes aggregate changes traceable back to individual queries rather than exposing only one headline number.

## Tie-breaking

Evaluation inherits the production ranker's deterministic ordering:

1. descending BM25 score;
2. case-folded source label;
3. span character start;
4. span ID.

A tied corpus can therefore be used in regression tests to assert exact rank and MRR behavior.

## Label validity

Gold relevance is workspace-specific.

If an evaluation case references a span ID that is not currently present in the workspace, VerityGraph returns an explicit validation error. It does not:

- reinterpret the ID;
- search another workspace;
- convert the missing label into a retrieval miss;
- silently remove it from the denominator.

This prevents stale benchmark files from producing misleading lower scores.

## Citation context exclusion

Citation discovery context is not part of retrieval evaluation.

The evaluator calls the production lexical ranker directly and does not score:

- citation neighbors;
- citation in-degree/out-degree;
- source relationship signals;
- graph centrality;
- source type;
- authority proxies.

This preserves the Phase 18 boundary: graph connectivity is discovery context, not direct relevance evidence.

## Persistence

Evaluation requests, gold labels, and metric results are not persisted as source truth.

The Evaluation Lab is an explicit benchmarking surface. Users may keep labelled datasets externally and submit them against a workspace, but VerityGraph does not silently mutate source provenance based on evaluation labels.

## User-interface contract

The browser exposes a Retrieval Evaluation Lab where users can paste labelled case JSON and choose K values.

It displays:

- case count;
- indexed span count;
- unique relevant span count;
- MRR;
- Recall@K;
- Precision@K;
- HitRate@K;
- per-case first relevant rank and reciprocal rank.

The UI also displays the guardrail:

```text
Retrieval metric ≠ factual accuracy, answer quality, authority, or truth.
```

## Non-claims

Good retrieval metrics do not prove:

- factual correctness;
- answer correctness;
- source authority;
- coverage of all possible user intents;
- robustness outside the labelled dataset;
- truth.

Metrics only measure ranking behavior against the supplied relevance judgements.

Likewise, one benchmark dataset is not sufficient evidence that a new retrieval method is generally superior.

## Rejected alternatives

### Evaluate a copied BM25 implementation

Rejected because benchmark drift from production would make the metrics unreliable.

### Treat missing gold spans as ordinary misses

Rejected because missing labels can indicate stale or wrong benchmark data rather than retrieval failure.

### Include citation neighbors as relevant by default

Rejected because graph connectivity does not establish query relevance.

### Report only top-1 accuracy

Rejected because retrieval systems need ranking-sensitive metrics and can have multiple relevant spans.

### Add semantic retrieval before measuring BM25

Rejected because there would be no reproducible baseline against which to quantify the tradeoff.

## Consequences

### Benefits

- retrieval changes can be measured against a stable production baseline;
- exact tie-breaking and metric semantics are regression tested;
- stale labels fail explicitly;
- per-query diagnostics expose where aggregate metrics move;
- semantic retrieval can later be accepted or rejected based on measured performance rather than intuition;
- evaluation remains independent from answer generation.

### Limitations

- relevance labels are manually supplied;
- no inter-annotator agreement workflow exists yet;
- the lab does not persist benchmark datasets;
- binary relevance is used; graded relevance/NDCG is not included yet;
- metrics are workspace- and dataset-specific;
- no statistical significance or confidence intervals are reported in this phase.

## Next extensions

1. define a versioned labelled benchmark fixture for repeatable retrieval experiments;
2. add a local semantic candidate channel without replacing BM25;
3. compare BM25 vs semantic vs fused retrieval on the same cases;
4. add reciprocal-rank fusion only if benchmark results justify it;
5. build a grounded evidence pack from the winning retrieval configuration;
6. add answer generation only after retrieval provenance and benchmark quality remain inspectable.
