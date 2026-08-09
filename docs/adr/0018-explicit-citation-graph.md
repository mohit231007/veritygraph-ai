# ADR 0018: Build Citation Topology Only from Uniquely Resolved Explicit Provenance

## Status

Accepted

## Context

VerityGraph now preserves explicit URL references, selected MediaWiki citation bridges, bibliographic identifier observations, and a strict distinction between shared identifier mentions and attested source identity.

That substrate is finally strong enough to project source-to-source citation topology without converting co-mentions or ambiguous resolution into graph edges.

The graph must remain a deterministic projection over persisted provenance rather than a second mutable truth store.

## Decision

VerityGraph exposes:

```text
GET /api/v1/workspaces/{workspace_id}/citation-graph
```

The response contains every current workspace source as a node plus directed source-to-source edges admitted by one of two deterministic mechanisms.

### URL-reference edge

A retained `SourceReference` may create an edge only when the existing URL-reference lineage resolves it to exactly one workspace source:

```text
SourceReference
    -> workspace_unique URL target
    -> citation edge
```

External/unresolved references remain counted but do not enter topology.

If several workspace sources share the matching URL identity, the reference remains ambiguous and no edge is created.

### Bibliographic-identifier edge

A `SourceIdentifier` may create an edge only when:

1. its role is `reference`; and
2. its `identity_target_resolution` is `workspace_unique`; and
3. the target is another source carrying `source_identity` for the same normalized DOI/arXiv/ISBN identity.

```text
reference-linked identifier
    -> uniquely attested source_identity target
    -> citation edge
```

Ordinary `mention` observations are never admitted to citation topology.

A shared DOI/arXiv/ISBN observation therefore cannot create an edge by itself.

## Edge aggregation

The graph has at most one deterministic directed edge per `(source_id, target_source_id)` pair.

If the same source pair is supported by both URL and bibliographic mechanisms, the graph retains one edge with both mechanisms and all underlying provenance IDs:

```text
mechanisms
url_reference_ids
identifier_ids
bibliographic_identities
evidence_count
```

The graph does not discard the lower-level provenance projections; users can still inspect reference and identifier lineage separately.

## Ambiguity policy

Ambiguous and unresolved evidence is excluded from topology rather than guessed.

The graph summary reports:

```text
unresolved_url_reference_count
ambiguous_url_reference_count
unresolved_identifier_reference_count
ambiguous_identifier_reference_count
```

This makes absence of an edge distinguishable from absence of a reference.

## Self-reference

A uniquely resolved explicit URL reference may point back to the same source. That edge is retained as an explicit self-reference and marked `self_edge`.

Bibliographic identity target resolution already excludes the current source from its candidate set, so identifier-based self-targets are not created by that mechanism.

## Non-claims

A citation-graph edge means only that VerityGraph retained explicit provenance that uniquely resolves from one workspace source to another.

It does **not** prove:

- factual support;
- endorsement;
- agreement;
- source quality;
- authority;
- causal dependence;
- copying;
- independence;
- correctness;
- truth.

A hyperlink can express many relationships besides scholarly citation, and a bibliographic reference can criticize or contradict its target.

For that reason the UI describes this as explicit citation/reference topology and displays a guardrail beside the graph.

## Deterministic projection

The citation graph is regenerated from:

```text
WorkspaceDetail
SourceReference lineage
SourceIdentifier lineage
```

It is not persisted as an independent truth representation.

No LLM, embedding model, registry lookup, external citation API, or fuzzy matcher participates in edge admission.

## Consequences

### Benefits

- source-to-source topology is now inspectable in the browser;
- every edge can be traced to exact persisted reference/identifier records;
- URL and bibliographic mechanisms can corroborate one directed source pair without duplicate graph edges;
- ambiguous and unresolved provenance remains visible without contaminating topology;
- shared identifier mentions cannot masquerade as citations;
- the graph can become a safe retrieval/navigation signal for future grounded RAG.

### Limitations

- edge intent and stance are not classified;
- unresolved external references remain outside topology until a matching source is ingested;
- duplicate attested targets remain ambiguous;
- no external citation registry is consulted;
- citation counts are workspace-relative rather than global scholarly metrics;
- graph centrality over explicit references is not yet promoted into source authority or truth scores.

## Next extensions

1. citation in/out-degree and path analytics as descriptive topology only;
2. filters by URL vs bibliographic mechanism;
3. citation intent/stance only after labelled evaluation;
4. hybrid evidence graph + citation graph retrieval;
5. grounded GraphRAG that returns source/span/reference provenance with every synthesized answer.
