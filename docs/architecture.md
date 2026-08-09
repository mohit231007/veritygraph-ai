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
              Entity + Relation + Evidence + Polarity
                               |
                               v
              Deterministic entity resolution
                  /                         \
        canonical entities          remapped assertions
                  \                         /
                   +------ Evidence ------+
                               |
                  +------------+------------+
                  |                         |
                  v                         v
         EvidenceGraph projection    Source comparison
          non-negated analytics      support + conflict
                  |                         |
                  +------------+------------+
                               |
                               v
                    Evidence review surfaces
                               |
                               v
                      future grounded RAG
```

## Core invariant

A source-derived graph assertion is valid only when its lineage is complete:

```text
GraphEdge -> Relation -> RelationEvidence -> SourceSpan -> SourceDocument
```

A relation also carries assertion polarity. For new runs the deterministic baseline currently retains explicit root negation as `negated`, otherwise `affirmed`. Historical relations created before polarity existed are migrated as `unknown`, never rewritten as affirmed after the fact.

Entity resolution may change which canonical entity ID a mention or relation points to, but it never changes the original mention text, evidence sentence, source span, or source document. The immutable analysis run records the resolver version used to make those identity decisions.

The graph is a projection of the immutable analysis run rather than a second source of truth. Changing a visual layout cannot rewrite evidence, entities, relations, polarity, analytics, or source lineage.

No generated response is allowed to rewrite source evidence. Response improvement creates a new response version; source truth and analysis-run provenance remain immutable.

## Domain boundaries

- `ingestion`: obtains permitted content and preserves source structure.
- `domain`: canonical source, analysis, entity, relation, polarity, evidence, graph, comparison, feedback, and run models.
- `nlp`: NER, relation extraction, explicit baseline polarity, deterministic entity resolution, and future calibrated confidence.
- `graph`: deterministic analysis-run projection, non-negated structural algorithms, paths, and future storage adapters.
- `comparison`: deterministic corroboration, source overlap, and strict evidence-backed contradiction candidates.
- `insights`: source-derived facts and computed graph observations.
- `rag`: optional local synthesis over explicitly selected evidence.
- `api`: HTTP contracts only; orchestration belongs in services.

## Entity identity boundary

The first resolver operates after local NLP extraction and before the completed run is persisted. It currently consolidates only explainable `ORG` aliases: legal-suffix variants and unique acronym/full-name matches. Ambiguous candidates remain separate.

Because resolution happens before graph and comparison projection, all downstream analytics see the same canonical identities. Original mention strings remain attached to the canonical entity with source/span/offset lineage, so normalization does not erase what the evidence actually said.

Relation remapping includes polarity in its aggregation identity. An affirmed and negated assertion with the same canonical subject, predicate, and object therefore remain separate evidence-bearing relations rather than being accidentally combined.

## Assertion polarity and contradiction boundary

The deterministic polarity baseline is intentionally narrower than natural-language inference. It records direct dependency-root negation and exposes the method used. It does not claim to solve negation scope, modality, temporal qualification, lexical contradiction, or factual truth.

Source comparison may create a `ContradictionCandidate` only when the same resolved subject-predicate-object has both affirmed and negated evidence and at least two distinct sources occur across the two evidence sides.

The following never creates a contradiction candidate by itself:

- another source being silent;
- a historical `unknown` relation;
- low pairwise overlap;
- different subjects, predicates, or objects;
- graph distance or centrality.

A contradiction candidate means only that VerityGraph retained incompatible source evidence worth reviewing. It does not decide which source is correct.

## Storage strategy

SQLite stores canonical sources, workspaces, immutable analysis runs, resolved entities, remapped polarity-aware relations, and evidence. Each analysis run stores its model, extractor, and resolver versions. Existing databases are migrated in place when new lineage fields are introduced; historical relation polarity defaults to `unknown` rather than receiving guessed semantics.

The current NetworkX evidence graph is regenerated from an analysis run rather than persisted as a separate mutable graph blob. Source comparison is likewise a deterministic projection. This keeps the product local-first while leaving room for Neo4j Community or PostgreSQL adapters if later workloads justify them.

## Graph analytics boundary

NetworkX is the backend analytical engine. It computes structural metrics such as PageRank, centrality, communities, components, density, and connection paths from one specific analysis run.

Explicitly negated relations remain visible as evidence edges but are excluded from the structural analytical projection and connection paths. This prevents `A did not acquire B` from creating the same positive connectivity as `A acquired B`. Historical `unknown` relations remain structurally usable so older runs preserve their previous graph behavior while exposing the uncertainty explicitly.

Cytoscape.js is the browser rendering and interaction layer. It can change layout, selection, and path highlighting, but it is not allowed to become the authoritative source for graph analytics or evidence lineage.

## Response improvement semantics

Two operations remain deliberately distinct:

1. **Improve response** — same analysis run and evidence set, plus user critique, creates a child `ResponseVersion`.
2. **Refresh analysis** — re-fetch/re-ingest permitted sources and create a new immutable `AnalysisRun`; answers may then use the refreshed evidence graph.

That distinction prevents a UI action from silently changing both evidence and wording at the same time.
