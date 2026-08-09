# Evidence Graph

## Purpose

The evidence graph is a deterministic projection of one immutable `AnalysisRun`. It does not re-run NLP, rewrite relationships, or create new source facts. It turns the run's persisted entities, relations, and evidence records into a graph-shaped analytical view.

```text
AnalysisRun
  |
  +-- Entity ---------------------------> GraphNode
  |
  +-- Relation -------------------------> GraphEdge
         |
         +-- RelationEvidence ----------> edge evidence inspector
                |
                +-- SourceSpan
                       |
                       +-- SourceDocument
```

The graph can therefore be regenerated from the same analysis run without changing source truth.

## Projection rules

- Every persisted analysis entity becomes a node, including isolated entities.
- Every persisted analysis relation remains a distinct evidence edge in the API response.
- Network analytics use a simple directed NetworkX projection in which repeated relations with the same source and target contribute evidence-support weight to the same analytical arc.
- The visualization layer does not own analytical truth; it renders the server result.
- Evidence remains attached to the original `relation_id`, never to a layout coordinate or visual edge index.

## Node analytics

Each graph node exposes:

- incoming degree;
- outgoing degree;
- NetworkX degree centrality;
- PageRank using evidence-support weight;
- unweighted betweenness centrality;
- greedy modularity community assignment on the undirected projection;
- exact entity mention count;
- number of distinct source documents containing the entity.

These values describe graph structure. They are **not** factual confidence scores.

## Graph-level analytics

The graph summary currently includes:

- node count;
- evidence-edge count;
- directed graph density;
- weakly connected component count;
- greedy modularity community count.

## PageRank semantics

PageRank is run on the directed analytical projection. Evidence count is used as an edge weight so a relation supported by more retained evidence contributes more structural weight than a relation with one evidence record.

This is an analytical ranking choice, not a claim that repeated evidence automatically makes a relationship true. Evidence quality, independence, source trust, contradictions, and calibrated factual confidence are separate future concerns.

## Communities

Community detection uses greedy modularity on the undirected weighted projection. This makes the result useful for exploratory clustering even when extracted predicates point in different directions.

Community IDs are run-local labels. `community=0` has no universal semantic meaning and should not be compared across independent analysis runs as though it were a stable ontology.

## Betweenness

Betweenness is currently unweighted. It answers a simple topology question: which entities sit on many shortest hop paths through the evidence graph?

This is useful for surfacing bridge entities without conflating evidence count with path distance.

## Connection paths

`GET /api/v1/analyses/{run_id}/graph/path` returns the fewest-hop **undirected** connection between two entities.

The API deliberately returns:

- `directed=false`;
- the ordered entity IDs;
- hop count;
- every persisted `relation_id` supporting each adjacent entity pair.

The UI labels this as an undirected evidence connection. It must not be presented as causal direction or proof that the first entity influences the last.

## Evidence inspector

Selecting a relation exposes:

- canonical source entity;
- extracted predicate;
- canonical target entity;
- extraction method;
- extraction-rule score;
- evidence count;
- distinct source count;
- every retained evidence sentence;
- source ID / user-facing filename;
- source span ID.

The rule score remains the extraction rule's relative strength and is not displayed as a factual probability.

## Accessibility and testability

The Cytoscape canvas is supplemented by semantic DOM entity and relation lists. This is intentional:

1. evidence should not become inaccessible because the graph is canvas-rendered;
2. keyboard users need a non-canvas path to inspect entities and relations;
3. browser E2E should test domain behavior rather than pixel coordinates;
4. future export/share workflows can reuse the same semantic structures.

## Rendering vs analytics

NetworkX runs on the backend and produces deterministic graph statistics for the current analysis run. Cytoscape.js is responsible for interactive rendering, selection, layout, and path highlighting only.

Changing from force-directed to circle or breadth-first layout therefore changes positions, not PageRank, communities, evidence, relations, or source lineage.

## Scaling path

The current design intentionally keeps the first graph local and dependency-light. Likely future scaling steps are:

1. cache graph projections by immutable `run_id` if rebuild latency becomes meaningful;
2. calculate expensive metrics selectively for very large runs;
3. introduce graph pagination/neighborhood APIs instead of sending every node to the browser;
4. add a Neo4j Community adapter only if operational graph-query needs justify it;
5. keep SQLite analysis/source truth and the graph adapter separated behind contracts.

No hosted graph database is required for the current product.
