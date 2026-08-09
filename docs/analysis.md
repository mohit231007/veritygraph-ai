# Analysis engine

VerityGraph's analysis layer consumes persisted `SourceSpan` records from a research workspace. It never bypasses ingestion to analyse anonymous raw strings.

## Current pipeline

```text
Workspace
   |
   +-- SourceDocument A -> SourceSpan[]
   +-- SourceDocument B -> SourceSpan[]
   +-- SourceDocument N -> SourceSpan[]
                           |
                           v
                    spaCy nlp.pipe()
                           |
                 +---------+----------+
                 |                    |
                 v                    v
               NER              dependency parse
                 |                    |
                 v                    v
              Entity              Relation
                 |                    |
              Mention           RelationEvidence
                 |                    |
                 +---------+----------+
                           |
                           v
                    AnalysisRun
                           |
                           v
                        SQLite
```

## AnalysisRun lineage

Every execution receives a new `run_id`. A completed result records the exact pipeline/model/extractor versions and corpus counts used for that run.

Re-running analysis does not overwrite the previous run. This matters because a future extractor may disagree with an older version and VerityGraph must be able to explain which implementation produced each graph edge or insight.

## Entity identity in the baseline

The first release consolidates exact normalized named entities only. For example, repeated `Microsoft` ORG mentions across three sources become one analysis entity with three mention records.

The baseline does **not** claim that `Microsoft`, `Microsoft Corp.`, and `MSFT` are the same entity. Alias/entity resolution is intentionally a later layer that can be evaluated independently and retain every original mention.

## Evidence-linked relationships

A relation is not accepted without evidence. Every `Relation` contains one or more evidence objects with:

- source ID;
- source-span ID;
- exact supporting sentence;
- sentence start/end offsets inside that span.

This lets future graph/UI layers answer:

> Why does this edge exist?

without re-running NLP or searching the corpus heuristically.

## Extraction score

`extraction_score` is the score assigned to a transparent extraction rule. It is **not** a calibrated probability that the relationship is factually true.

Current rule strengths:

| Pattern | Score | Method |
|---|---:|---|
| subject + direct object | 0.92 | `dependency_subject_object` |
| passive agent normalisation | 0.90 | `dependency_passive_agent` |
| subject + prepositional object | 0.84 | `dependency_subject_preposition_object` |

These values can help rank baseline extraction candidates, but they must not be marketed as model accuracy or factual confidence. A later labelled benchmark will measure precision, recall and F1 and can determine whether score calibration is justified.

## Complexity

Let:

- `T` = total tokens in all workspace spans;
- `M` = extracted entity mentions;
- `R` = emitted relation candidates.

The dominant cost is spaCy inference over `T` tokens. Post-processing traverses entity mentions and sentence-local candidates. Because entities are indexed by sentence once, relation preparation is approximately `O(T + M + R)` after the NLP pipeline rather than repeatedly scanning every entity for every sentence.

Memory is dominated by the spaCy documents plus persisted analysis objects for the current run. `nlp.pipe()` batches model execution to avoid invoking the pipeline separately for every evidence span.

## API

```text
POST /api/v1/workspaces/{workspace_id}/analyses
GET  /api/v1/workspaces/{workspace_id}/analyses
GET  /api/v1/workspaces/{workspace_id}/analyses/latest
GET  /api/v1/analyses/{run_id}
```

## Next analysis improvements

1. alias/entity resolution with explicit merge provenance;
2. graph repository consuming persisted relation IDs;
3. rule-level evaluation by relation type;
4. labelled golden dataset and precision/recall/F1 reporting;
5. optional local LLM extractor behind the same interface;
6. deterministic vs local-LLM vs hybrid benchmark including latency and memory;
7. feedback-derived error analysis from the future Insight Studio.
