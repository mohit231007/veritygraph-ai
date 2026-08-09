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
           raw Entity           raw Relation
              Mention           RelationEvidence
                 |                    |
                 +---------+----------+
                           |
                           v
            DeterministicEntityResolver
                 |                    |
                 v                    v
        canonical Entity        remapped Relation
              Mention           RelationEvidence
                 |                    |
                 +---------+----------+
                           |
                           v
                    AnalysisRun
                           |
                           v
                        SQLite
                           |
                           v
                  EvidenceGraph
```

## AnalysisRun lineage

Every execution receives a new `run_id`. A completed result records the exact pipeline, model, extractor, and resolver versions plus corpus/result counts used for that run.

Current resolver lineage is `deterministic-org-aliases-v1`. Historical runs created before resolver lineage was introduced are migrated with `resolver_version = "none"`; they are not retroactively rewritten as though resolution had been applied.

Re-running analysis does not overwrite the previous run. This matters because a future extractor or resolver may disagree with an older version and VerityGraph must be able to explain which implementation produced each graph edge or insight.

## Entity identity in the baseline

The analysis engine first consolidates exact normalized named entities. It then applies a conservative deterministic resolver to `ORG` entities before the completed run is persisted.

The current resolver can merge:

- trailing legal-name variants such as `Microsoft` and `Microsoft Corporation`;
- an uppercase acronym such as `IBM` when exactly one multi-token organization in the current corpus expands to that acronym.

Ambiguous acronym candidates remain separate rather than being guessed. Original mention text is always retained with source/span/character provenance and is shown as an alias in the UI when it differs from the selected canonical name.

The resolver does not yet use fuzzy string matching, embeddings, external registries, web lookup, coreference resolution, or LLM judgement. Those techniques require their own labelled evaluation before they are allowed to alter persisted graph identity.

## Relation remapping after resolution

When aliases collapse into a canonical entity:

1. relation subject/object IDs are remapped to the canonical entity IDs;
2. relations that become alias-only self-loops are removed;
3. identical canonical `(subject, predicate, object)` relations are consolidated;
4. distinct evidence sentences remain attached to the surviving relation;
5. the strongest extraction-rule score/method is retained for the consolidated relation.

This prevents an alias from creating duplicate graph nodes or duplicate edges while keeping the evidence that supported each original extraction.

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

These values can help rank baseline extraction candidates, but they must not be marketed as model accuracy or factual confidence. The labelled benchmark measures precision, recall and F1 and can later determine whether score calibration is justified.

## Complexity

Let:

- `T` = total tokens in all workspace spans;
- `M` = extracted entity mentions;
- `E` = extracted entities;
- `R` = emitted relation candidates.

The dominant cost is spaCy inference over `T` tokens. Extraction post-processing traverses entity mentions and sentence-local relation candidates. The deterministic resolver builds normalized organization groups and remaps relations, keeping normal use approximately linear in `E + M + R` after NLP, apart from small in-memory group/index operations.

Memory is dominated by the spaCy documents plus analysis objects for the current run. `nlp.pipe()` batches model execution to avoid invoking the pipeline separately for every evidence span.

## API

```text
POST /api/v1/workspaces/{workspace_id}/analyses
GET  /api/v1/workspaces/{workspace_id}/analyses
GET  /api/v1/workspaces/{workspace_id}/analyses/latest
GET  /api/v1/analyses/{run_id}
```

## Evaluation

The relation benchmark now executes the same production sequence used by the application:

```text
spaCy extraction -> deterministic entity resolution -> exact-triple evaluation
```

Its report includes model, pipeline, extractor, and resolver versions. The starter gold set is deliberately small and proves the evaluation path only; its scores are not production-accuracy claims.

## Next analysis improvements

1. labelled entity-resolution benchmark with pairwise and cluster metrics;
2. explicit parenthetical alias handling and curated alias overrides;
3. contradiction-aware evidence and source comparison;
4. rule-level evaluation by relation type;
5. optional local LLM extractor behind the same interface;
6. deterministic vs local-LLM vs hybrid benchmark including latency and memory;
7. feedback-derived error analysis from the future Insight Studio.
