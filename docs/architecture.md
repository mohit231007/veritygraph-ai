# Architecture

## Design goal

VerityGraph turns heterogeneous unstructured sources into a single evidence-aware intelligence model. Ingestion is separated from analysis so PDF, DOCX, Wikipedia, and web inputs do not create parallel NLP implementations.

## Current flow

```text
Document upload ─┐
Wikipedia ────────┼─> SourceDocument / SourceSpan / SourceReference / SourceIdentifier
Public URL ───────┘             |
                  +-------------+--------------------+
                  |             |                    |
                  v             v                    v
         Persistent workspace  URL reference     Bibliographic
                  |            lineage            identifier lineage
                  |             |                 shared observations
                  |             |                 + source attestation
                  v             |                    |
         Immutable AnalysisRun  |                    |
                  |             |                    |
                  v             |                    |
        Local NLP extraction    |                    |
                  |             |                    |
Entity + Relation + Evidence + Assertion Qualifiers  |
                  |                                  |
                  v                                  |
     Deterministic entity resolution                 |
         /                       \                    |
canonical entities         remapped assertions       |
         \                       /                    |
          +------ Evidence -----+                    |
                  |                                  |
         +--------+--------+                         |
         |                 |                         |
         v                 v                         |
EvidenceGraph       Source comparison                |
 projection         support + scoped conflict        |
 analytics          + relationship signals           |
         |                 |                         |
         +-----------------+-------------------------+
                           |
                           v
                 Evidence review surfaces
                           |
                           v
                   future grounded RAG
```

## Core invariants

A source-derived graph assertion is valid only when its lineage is complete:

```text
GraphEdge -> Relation -> RelationEvidence -> SourceSpan -> SourceDocument
```

An explicit source reference is valid only when the observable target and provenance are retained:

```text
SourceDocument -> SourceReference -> target URL
                       |
                       +-> SourceSpan when deterministic span mapping exists
                       +-> page / paragraph locator when format metadata exposes it
                       +-> citation marker / bibliography text when MediaWiki exposes it
```

A page or paragraph locator identifies where a link object was observed. It does not imply that a hidden target URL was present inside canonical NLP text.

A bibliographic identifier observation retains its semantic role separately:

```text
SourceDocument -> SourceIdentifier
                       |
                       +-> mention
                       +-> reference
                       +-> source_identity
```

A shared identifier observation is not source identity. `source_identity` is attested only when the source acquisition URL itself uses a supported DOI resolver or arXiv work URL.

A workspace reference projection may resolve the target URL to one or more currently ingested `SourceDocument` records, but URL matching never rewrites the original reference.

A new relation also carries conservative qualifiers:

```text
polarity        = unknown | affirmed | negated
modality        = unknown | asserted | modal
temporal_years  = sorted explicit four-digit years in the sentence
```

New runs detect direct root negation, direct modal/future auxiliaries, and explicit sentence years. Historical relations created before a qualifier existed are never retroactively guessed; their migrated qualifier remains `unknown` or `historical_unknown`.

Entity resolution may change which canonical entity ID a mention or relation points to, but it never changes original mention text, evidence sentence, source span, source document, polarity, modality, or time scope.

The graph, comparison, URL-reference, and bibliographic-identifier layers are deterministic projections rather than second mutable truth stores.

## Domain boundaries

- `ingestion`: obtains permitted content and preserves source structure, observable references, format-level links, selected MediaWiki citation bridges, and bibliographic identifiers.
- `domain`: canonical source, source reference, source identifier, lineage, analysis, entity, qualified relation, evidence, graph, comparison, feedback, and run models.
- `nlp`: NER, relation extraction, conservative assertion qualifiers, deterministic entity resolution, and future calibrated adapters.
- `graph`: deterministic analysis-run projection, established structural algorithms, paths, and future storage adapters.
- `comparison`: deterministic corroboration, source overlap, source-relationship review signals, and strict evidence-backed scoped contradiction candidates.
- `reference-lineage`: deterministic explicit URL-reference projection over current workspace sources; no citation-intent inference.
- `identifier-lineage`: deterministic DOI/arXiv/ISBN observation projection plus explicit acquisition-URL source identity attestation; no registry or citation-intent inference.
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

## Explicit reference-lineage boundary

`SourceReference` stores explicit HTTP(S) targets observed during canonical source ingestion.

The currently supported reference inputs are:

- URLs visibly present in retained document/web/Wikipedia evidence spans;
- public HTML anchors whose enclosing paragraph/list/table-row maps to retained main-content evidence;
- external DOCX hyperlink relationships in top-level document paragraphs;
- PDF URI link annotations;
- selected MediaWiki inline citations resolved from `cite_note` markers to external URLs;
- direct external links in explicitly selected MediaWiki reference-list sections.

MediaWiki citing prose, citation label/marker, bibliography entry text, and external target remain separate provenance fields. Citations belonging only to unselected article sections are not imported.

DOCX hyperlink display text is kept in canonical visible paragraph text, while the relationship target URL remains separate reference metadata unless the URL was visibly printed. PDF annotation targets likewise remain reference metadata; they are never injected into page NLP text merely because the page contains a clickable annotation.

`SourceReference` may retain `span_id`, `page_number`, and `paragraph_number`. A span is used only when deterministic mapping exists. A PDF link can retain a page locator even when the page has no matching readable span.

Reference URL identity is exact and conservative: scheme/hostname normalization, IDNA hostname handling, default-port removal, path/query retention, and fragment removal. No redirect fetching, canonical-tag interpretation, or semantic URL equivalence occurs during the workspace projection.

Workspace resolution has three states:

```text
external
workspace_unique
workspace_ambiguous
```

If several workspace sources share a matching normalized URL, every candidate is retained and the edge is ambiguous. Import order is never used to choose a target.

An explicit link does not prove quotation, support, endorsement, dependence, copying, or truth. Absence of an extracted reference also does not prove that a source contains no citation. Unsupported DOCX table/header/footer/footnote hyperlinks and non-URL bibliographic forms can still remain outside the current deterministic extraction boundary.

Reference lineage currently does not alter entity/relation extraction, graph structure, corroboration, contradiction candidates, source-relationship signals, or rule scores.

## Bibliographic identifier and source-identity boundary

`SourceIdentifier` preserves explicit DOI, arXiv, and valid ISBN observations.

Three roles are intentionally distinct:

```text
mention         # identifier observed in retained source text
reference       # identifier observed in retained reference text or supported reference URL
source_identity # acquisition URL itself explicitly identifies the ingested work
```

DOI identity comparison folds ASCII case while retaining the raw observation. arXiv stores the base identifier as the identity key and an optional `vN` suffix separately. ISBN extraction is label-gated and checksum validated; a valid ISBN-10 normalizes to the equivalent ISBN-13 identity.

Only supported DOI resolver and arXiv acquisition URLs create `source_identity`. A DOI-shaped path on an arbitrary publisher host does not. Uploaded documents do not become source-identity-attested merely because their body contains a DOI, arXiv ID, or ISBN.

The identifier-lineage projection exposes two different match concepts:

```text
shared observation
    -> another source also retained the normalized identifier

attested identity target
    -> another source has source_identity for the normalized identifier
```

The current source is excluded from both candidate sets. Multiple candidates remain ambiguous; import order never breaks ties.

A shared identifier does not prove source identity. A source-identity attestation does not prove citation, endorsement, authorship, factual support, dependence, copying, authority, or truth. No DOI, arXiv, ISBN, Crossref, DataCite, OpenAlex, or other registry request occurs during this projection.

## Storage strategy

SQLite stores canonical sources, source spans, explicit source references, bibliographic identifier observations, workspaces, immutable analysis runs, resolved entities, qualified relations, and evidence. Each run stores its model, extractor, and resolver versions.

Existing databases are migrated in place. Historical sources are never silently reinterpreted: old sources have zero reference/identifier rows unless those records were captured when the source was ingested. Existing reference rows receive additive nullable provenance columns without guessed backfill. Historical polarity/modality are `unknown`; historical temporal method is `historical_unknown`; explicit year lists remain empty rather than receiving reconstructed dates.

NetworkX graphs, source comparisons, workspace reference lineage, and bibliographic identifier lineage are regenerated from persisted canonical records rather than stored as separate mutable truth representations.

Source relationship signals use persisted source metadata (`content_hash`, URL) and retained relation evidence. Reference lineage uses persisted `SourceReference` rows plus canonical/requested/final URL metadata. Identifier lineage uses persisted `SourceIdentifier` observations and their explicit roles.

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
