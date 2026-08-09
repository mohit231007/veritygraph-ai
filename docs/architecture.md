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
                               v
                     Local NLP extraction
                               |
                  Raw Entity + Relation + Evidence
                               |
                               v
              Deterministic entity resolution
                  /                         \
        canonical entities          remapped relations
                  \                         /
                   +------ Evidence ------+
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

Entity resolution may change which canonical entity ID a mention or relation points to, but it never changes the original mention text, evidence sentence, source span, or source document. The immutable analysis run records the resolver version used to make those identity decisions.

The graph is a projection of the immutable analysis run rather than a second source of truth. Changing a visual layout cannot rewrite evidence, entities, relations, analytics, or source lineage.

No generated response is allowed to rewrite source evidence. Response improvement creates a new response version; source truth and analysis-run provenance remain immutable.

## Domain boundaries

- `ingestion`: obtains permitted content and preserves source structure.
- `domain`: canonical source, analysis, entity, relation, evidence, graph, feedback, and run models.
- `nlp`: NER, relation extraction, deterministic entity resolution, and future calibrated confidence.
- `graph`: deterministic analysis-run projection, algorithms, paths, and future storage adapters.
- `insights`: source-derived facts and computed graph observations.
- `rag`: optional local synthesis over explicitly selected evidence.
- `api`: HTTP contracts only; orchestration belongs in services.

## Entity identity boundary

The first resolver operates after local NLP extraction and before the completed run is persisted. It currently consolidates only explainable `ORG` aliases: legal-suffix variants and unique acronym/full-name matches. Ambiguous candidates remain separate.

Because resolution happens before graph projection, all downstream analytics see the same canonical identities. Original mention strings remain attached to the canonical entity with source/span/offset lineage, so normalization does not erase what the evidence actually said.

## Storage strategy

SQLite stores canonical sources, workspaces, immutable analysis runs, resolved entities, remapped relations, and evidence. Each analysis run stores its model, extractor, and resolver versions. Existing databases are migrated in place when new lineage fields are introduced.

The current NetworkX evidence graph is regenerated from an analysis run rather than persisted as a separate mutable graph blob. This keeps the product local-first while leaving room for Neo4j Community or PostgreSQL adapters if later workloads justify them.

## Graph analytics boundary

NetworkX is the backend analytical engine. It computes structural metrics such as PageRank, centrality, communities, components, density, and connection paths from one specific analysis run.

Cytoscape.js is the browser rendering and interaction layer. It can change layout, selection, and path highlighting, but it is not allowed to become the authoritative source for graph analytics or evidence lineage.

## Response improvement semantics

Two operations remain deliberately distinct:

1. **Improve response** — same analysis run and evidence set, plus user critique, creates a child `ResponseVersion`.
2. **Refresh analysis** — re-fetch/re-ingest permitted sources and create a new immutable `AnalysisRun`; answers may then use the refreshed evidence graph.

That distinction prevents a UI action from silently changing both evidence and wording at the same time.
