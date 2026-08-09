# Architecture

## Design goal

VerityGraph turns heterogeneous unstructured sources into a single evidence-aware intelligence model. Ingestion is separated from analysis so PDF, DOCX, Wikipedia, and web inputs do not create parallel NLP implementations.

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
      Entity + Relation + Evidence + Assertion Qualifiers
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
          established analytics      support + scoped conflict
                  |                  + relationship signals
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

A new relation also carries conservative qualifiers:

```text
polarity        = unknown | affirmed | negated
modality        = unknown | asserted | modal
temporal_years  = sorted explicit four-digit years in the sentence
```

New runs detect direct root negation, direct modal/future auxiliaries, and explicit sentence years. Historical relations created before a qualifier existed are never retroactively guessed; their migrated qualifier remains `unknown` or `historical_unknown`.

Entity resolution may change which canonical entity ID a mention or relation points to, but it never changes original mention text, evidence sentence, source span, source document, polarity, modality, or time scope.

The graph and comparison layers are deterministic projections of one immutable analysis run rather than second mutable truth stores.

## Domain boundaries

- `ingestion`: obtains permitted content and preserves source structure.
- `domain`: canonical source, analysis, entity, qualified relation, evidence, graph, comparison, feedback, and run models.
- `nlp`: NER, relation extraction, conservative assertion qualifiers, deterministic entity resolution, and future calibrated adapters.
- `graph`: deterministic analysis-run projection, established structural algorithms, paths, and future storage adapters.
- `comparison`: deterministic corroboration, source overlap, source-relationship review signals, and strict evidence-backed scoped contradiction candidates.
- `insights`: source-derived facts and computed graph observations.
- `rag`: optional local synthesis over explicitly selected evidence.
- `api`: HTTP contracts only; orchestration belongs in services.

## Entity and assertion identity boundary

The resolver operates after local NLP extraction and before the completed run is persisted. It currently consolidates only explainable `ORG` aliases: legal-suffix variants and unique acronym/full-name matches. Ambiguous candidates remain separate.

Downstream assertion identity includes:

```text
canonical subject
predicate
canonical object
polarity
modality
explicit year set
```

This prevents evidence such as `acquired in 2018`, `did not acquire in 2019`, and `may acquire in 2027` from being collapsed into one relation simply because the subject, predicate, and object match.

## Contradiction boundary

The deterministic qualifier baseline is intentionally narrower than natural-language inference. A `ContradictionCandidate` requires:

1. identical resolved subject, predicate, and object;
2. affirmed and negated evidence;
3. modality `asserted` on both opposing sides;
4. compatible time scope;
5. at least two distinct sources across the opposing evidence.

Time compatibility fails closed:

- both unscoped -> compatible;
- overlapping explicit years -> compatible;
- disjoint explicit years -> not compatible;
- one scoped and one unscoped -> ambiguous, therefore not promoted automatically.

The following never creates a contradiction candidate by itself:

- another source being silent;
- a modal/future assertion;
- a historical `unknown` qualifier;
- disjoint or one-sided explicit year scope;
- low pairwise overlap;
- graph distance or centrality.

A candidate means only that VerityGraph retained incompatible evidence worth reviewing. It does not decide which source is correct.

## Source relationship boundary

Distinct source IDs establish storage/run membership, not independent reporting.

The comparison projection therefore exposes evidence diversity and pairwise relationship review signals separately from ordinary claim overlap.

For a qualified relation, the projection records:

```text
source_count
distinct_content_fingerprint_count
distinct_evidence_text_count
```

For each source pair it records a `SourceRelationshipSignal` containing:

```text
normalized origin hosts
exact persisted content-fingerprint match
exact normalized supporting-text overlap count
relation IDs with exact evidence overlap
review reasons
possible_derivation_signal
```

`possible_derivation_signal` is raised only by an exact content-fingerprint match or exact normalized supporting-text overlap on the same resolved relation. Same-origin host is contextual and is not sufficient by itself.

These signals are intentionally non-causal. They do not prove copying, common upstream sourcing, editorial dependence, source independence, authority, or factual truth. Absence of a detected signal does not prove independence.

Source relationship signals currently do not change graph topology, contradiction promotion, or extraction scores. They are review context over the same immutable run.

## Storage strategy

SQLite stores canonical sources, workspaces, immutable analysis runs, resolved entities, qualified relations, and evidence. Each run stores its model, extractor, and resolver versions.

Existing databases are migrated in place. Historical polarity/modality are `unknown`; historical temporal method is `historical_unknown`; explicit year lists remain empty rather than receiving reconstructed dates.

NetworkX graphs and source comparisons are regenerated from the immutable analysis run rather than persisted as separate mutable truth representations.

Source relationship signals use already persisted source metadata (`content_hash`, URL) and retained relation evidence. No new mutable truth table is introduced for the v4 comparison projection.

## Graph analytics boundary

NetworkX computes PageRank, centrality, communities, components, density, and connection paths from one specific analysis run.

Explicit `negated` and `modal` relations remain visible as evidence edges but are excluded from structural analytics and connection paths. Therefore neither:

```text
A did not acquire B
```

nor:

```text
A may acquire B
```

can create the same established connectivity as:

```text
A acquired B
```

Historical `unknown` qualifiers remain structurally usable so older immutable runs preserve prior behavior while exposing uncertainty explicitly.

Cytoscape.js is the browser rendering and interaction layer. Layout and selection cannot rewrite backend analytics or evidence lineage.

## Response improvement semantics

Two operations remain deliberately distinct:

1. **Improve response** — same analysis run and evidence set, plus user critique, creates a child `ResponseVersion`.
2. **Refresh analysis** — re-fetch/re-ingest permitted sources and create a new immutable `AnalysisRun`; answers may then use the refreshed evidence graph.

This prevents a UI action from silently changing both evidence and wording at the same time.
