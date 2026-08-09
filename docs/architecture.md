# Architecture

## Design goal

VerityGraph turns heterogeneous unstructured sources into a single evidence-aware intelligence model. Ingestion is intentionally separated from analysis so PDF, DOCX, Wikipedia, and web inputs do not create parallel NLP implementations.

## Target flow

```text
Document upload ─┐
Wikipedia ────────┼─> SourceDocument / SourceSpan
Public URL ───────┘             |
                               v
                         NLP / extraction
                               |
                  Entity + Relation + Evidence
                               |
                         Knowledge graph
                     /          |          \
                Analytics   Evidence UI   GraphRAG
```

## Core invariant

A source-derived graph relation is valid only when its lineage is complete:

```text
Relation -> Evidence -> SourceSpan -> SourceDocument
```

No generated response is allowed to rewrite source evidence. Response improvement creates a new response version; source truth and analysis-run provenance remain immutable.

## Planned domain boundaries

- `ingestion`: obtains permitted content and preserves source structure.
- `domain`: canonical source, entity, relation, evidence, feedback, and run models.
- `nlp`: NER, relation extraction, entity resolution, confidence.
- `graph`: storage abstraction, graph construction, algorithms and queries.
- `insights`: source-derived facts and computed graph observations.
- `rag`: optional local synthesis over explicitly selected evidence.
- `api`: HTTP contracts only; orchestration belongs in services.

## Storage strategy

Phase 1 starts with SQLite metadata and NetworkX graphs to keep the product zero-dependency and local-first. Neo4j Community and PostgreSQL are adapters, not requirements.

## Response improvement semantics

Two operations remain deliberately distinct:

1. **Improve response** — same analysis run and evidence set, plus user critique, creates a child `ResponseVersion`.
2. **Refresh analysis** — re-fetch/re-ingest permitted sources and create a new immutable `AnalysisRun`; answers may then use the refreshed evidence graph.

That distinction prevents a UI action from silently changing both evidence and wording at the same time.
