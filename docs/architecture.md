# Architecture

## Design goal

VerityGraph turns heterogeneous unstructured sources into a single evidence-aware intelligence model. Ingestion is intentionally separated from analysis so PDF, DOCX, Wikipedia, and web inputs do not create parallel NLP implementations.

## Current flow

```text
Document upload ─┐
Wikipedia ────────┼─> SourceDocument / SourceSpan
Public URL ───────┘             |
                               v
                      Persistent workspace
                               |
                               v
                      Immutable AnalysisRun
                               |
                  Entity + Relation + Evidence
                               |
                               v
                     EvidenceGraph projection
                     /          |          \
                Analytics   Evidence UI   future GraphRAG
```

## Core invariant

A source-derived graph relation is valid only when its lineage is complete:

```text
GraphEdge -> Relation -> RelationEvidence -> SourceSpan -> SourceDocument
```

The graph is a projection of the immutable analysis run rather than a second source of truth. Changing a visual layout cannot rewrite evidence, entities, relations, analytics, or source lineage.

No generated response is allowed to rewrite source evidence. Response improvement creates a new response version; source truth and analysis-run provenance remain immutable.

## Domain boundaries

- `ingestion`: obtains permitted content and preserves source structure.
- `domain`: canonical source, analysis, entity, relation, evidence, graph, feedback, and run models.
- `nlp`: NER, relation extraction, entity resolution, and future calibrated confidence.
- `graph`: deterministic analysis-run projection, algorithms, paths, and future storage adapters.
- `insights`: source-derived facts and computed graph observations.
- `rag`: optional local synthesis over explicitly selected evidence.
- `api`: HTTP contracts only; orchestration belongs in services.

## Storage strategy

SQLite stores canonical sources, workspaces, immutable analysis runs, entities, relations, and evidence. The current NetworkX evidence graph is regenerated from an analysis run rather than persisted as a separate mutable graph blob.

This keeps the product local-first while leaving room for Neo4j Community or PostgreSQL adapters if later workloads justify them.

## Graph analytics boundary

NetworkX is the backend analytical engine. It computes structural metrics such as PageRank, centrality, communities, components, density, and connection paths from one specific analysis run.

Cytoscape.js is the browser rendering and interaction layer. It can change layout, selection, and path highlighting, but it is not allowed to become the authoritative source for graph analytics or evidence lineage.

## Response improvement semantics

Two operations remain deliberately distinct:

1. **Improve response** — same analysis run and evidence set, plus user critique, creates a child `ResponseVersion`.
2. **Refresh analysis** — re-fetch/re-ingest permitted sources and create a new immutable `AnalysisRun`; answers may then use the refreshed evidence graph.

That distinction prevents a UI action from silently changing both evidence and wording at the same time.
