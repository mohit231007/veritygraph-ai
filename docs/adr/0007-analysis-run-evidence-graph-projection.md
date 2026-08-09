# ADR 0007: Project immutable analysis runs into evidence graphs

- Status: Accepted
- Date: 2026-08-09

## Context

VerityGraph now persists canonical sources, source spans, workspaces, immutable analysis runs, named entities, extracted relations, and exact relation evidence. The next product layer needs graph exploration and analytics without weakening the central provenance invariant.

A tempting implementation would store a second independently mutable graph representation or let the frontend construct a graph directly from whatever data happens to be visible. Both approaches introduce avoidable drift:

- graph state could disagree with the persisted analysis run;
- a visual edge could lose its source evidence lineage;
- re-layout or client-side transformation could accidentally become analytical truth;
- graph-specific storage would become mandatory before there is evidence it is needed.

## Decision

An evidence graph is a deterministic, regenerable projection of one immutable `AnalysisRun`.

```text
AnalysisRun
   |
   +--> Entity ----------> GraphNode
   |
   +--> Relation --------> GraphEdge --------> RelationEvidence
                                                |
                                                v
                                         SourceSpan -> SourceDocument
```

The backend performs graph construction and analytics with NetworkX. Cytoscape.js renders the returned graph and manages visual interaction only.

### Analytical projection

The API preserves every persisted relation as its own `GraphEdge`. For graph algorithms, repeated relations sharing the same source and target are collapsed into one directed analytical arc whose weight is accumulated evidence support.

This avoids converting visual parallel-edge details into algorithm-specific complexity while preserving the original relation records in the response.

### Initial analytics

The first graph release provides:

- directed in/out degree;
- degree centrality;
- evidence-weighted PageRank;
- unweighted betweenness centrality;
- weakly connected components;
- density;
- greedy modularity communities on an undirected weighted projection;
- fewest-hop undirected entity connection paths.

### Path semantics

Connection paths are explicitly undirected because the initial user question is connectivity: “How are these entities connected in the retained evidence?” The response marks `directed=false` and includes the exact relation IDs supporting every hop.

It must not be presented as a causal chain.

### Rendering semantics

Changing a Cytoscape layout changes only visual coordinates. It does not change graph metrics, evidence, extraction scores, entity identity, or source lineage.

The UI also exposes semantic DOM entity/relation lists so evidence inspection does not depend on canvas coordinates.

## Alternatives considered

### Store NetworkX objects or serialized graph blobs in SQLite

Rejected for the initial release. The graph can be rebuilt from immutable persisted analysis data, so a second stored representation creates invalidation and migration work without adding source truth.

### Require Neo4j immediately

Rejected. Neo4j may become a useful adapter for larger graph workloads, but making it mandatory now would add deployment and operational complexity to a local-first product before graph scale requires it.

### Compute all graph analytics in the browser

Rejected. This would make browser code the source of analytical truth, complicate reproducibility, duplicate logic across clients, and make API consumers receive weaker results than the UI.

### Treat evidence count as factual confidence

Rejected. Evidence count is currently only a structural support weight. Repetition does not establish source independence, trustworthiness, contradiction handling, or calibrated truth probability.

## Consequences

### Positive

- graph lineage is inherited directly from the immutable analysis run;
- graph results are reproducible and API-accessible;
- the frontend remains a visualization/interaction client;
- local execution stays free and simple;
- a future graph database can be added as an adapter rather than a prerequisite;
- browser E2E can verify evidence behavior through semantic controls instead of fragile pixel interaction.

### Trade-offs

- NetworkX calculations are in-memory and may become expensive for very large runs;
- PageRank/community results are recalculated when the graph endpoint is called until caching is introduced;
- exact entity resolution remains intentionally conservative, so aliases can still appear as separate graph nodes;
- the initial path API optimizes hop count, not trust, evidence quality, chronology, or causal relevance.

## Follow-up decisions

Future ADRs should separately address:

- entity alias/coreference resolution;
- contradiction-aware edge state;
- graph projection caching and large-graph neighborhood APIs;
- optional Neo4j/PostgreSQL adapters;
- calibrated source/evidence quality scoring;
- GraphRAG retrieval semantics.
