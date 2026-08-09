# VerityGraph build status

This document records the engineering sequence independently of chat/project history.

## Implemented foundations

### Phase 0 — production skeleton

- FastAPI API
- React + TypeScript + Vite frontend
- Nginx reverse proxy
- Docker Compose
- pytest / Ruff / Playwright / GitHub Actions
- cross-platform QA runner
- local-first / zero-mandatory-cost architecture

### Phase 1 — document provenance

- PDF via PyMuPDF
- DOCX via python-docx
- TXT
- upload validation and limits
- canonical `SourceDocument` + `SourceSpan`
- source preview
- browser E2E

### Phase 2 — Wikipedia intelligence

- official MediaWiki search API
- revision-aware article outline
- section selection
- deterministic CI provider
- Wikipedia section/paragraph provenance
- browser E2E

### Phase 3 — secure public URL intelligence

- HTTP(S)-only public retrieval
- SSRF-oriented IP/DNS validation
- redirect revalidation
- body/MIME/time limits
- Trafilatura main-content extraction from already-approved bytes
- canonical public-source provenance
- browser E2E

### Phase 4 — persistent multi-source research workspaces

- SQLite canonical source/span persistence
- named workspaces
- many-to-many workspace/source membership
- persistent Docker volume
- non-root backend container
- hermetic disposable QA volume
- browser reload persistence E2E

## Phase 5 — evidence-linked local NLP

Implemented on `agent/nlp-analysis-baseline`:

- local spaCy `en_core_web_sm` baseline
- versioned/immutable `AnalysisRun`
- model/pipeline/extractor lineage
- graph-relevant named-entity extraction
- exact normalized entity consolidation across workspace sources
- entity mentions linked to source + span + character offsets
- active subject/object relation extraction
- subject/preposition/object relation extraction
- passive-agent normalization to semantic active direction
- relation evidence linked to exact supporting sentence + source/span
- multi-source evidence aggregation for the same relation
- SQLite persistence for runs/entities/mentions/relations/evidence
- Analysis API and frontend panel
- latest-analysis restoration after reload
- explicit `Rule score != factual probability` product semantics
- starter labelled triple benchmark and exact precision/recall/F1 machinery

## Stacked PR chain

```text
main
  |
  +-- PR #2 production foundation
       |
       +-- PR #3 document ingestion
            |
            +-- PR #4 Wikipedia ingestion
                 |
                 +-- PR #5 secure public URL ingestion
                      |
                      +-- PR #6 SQLite workspaces
                           |
                           +-- PR #7 local NLP analysis
```

The stack is intentional: each feature can be reviewed as an independently meaningful layer instead of one unreviewable monolithic change.

## Next gates

### Phase 6 — evidence graph and graph analytics

Planned:

- graph repository contract
- entity nodes and evidence-linked relation edges
- NetworkX default local adapter
- graph JSON API
- interactive frontend exploration
- degree and betweenness centrality
- PageRank
- connected components
- community detection
- shortest paths
- bridge entities
- edge/source support counts
- graph E2E: relation -> edge -> click -> exact supporting evidence

### Phase 7 — entity resolution

Planned conservatively and separately from raw NER:

- aliases retained as provenance, never overwritten
- acronym/legal-suffix candidates
- resolution method and score
- manual split/merge corrections
- gold evaluation of merge precision before aggressive automation

### Phase 8 — Insight Studio

Planned:

- generated/source-derived/computed-insight labels
- response versions
- thumbs/rating + reason categories + free-text critique
- claim-level accept/reject/review
- Improve Response with frozen evidence
- Refresh Analysis as a separate operation
- V1/V2 comparison
- keep preferred version
- copy plain text / Markdown / cited text
- download Markdown / TXT / JSON / CSV / GraphML; report formats later
- reproducible snapshot/share package
- Evidence Health and “Why should I trust this?” explanation

### Phase 9 — multi-source intelligence

Planned:

- cross-source support counts
- single-source claims
- agreement candidates
- temporal/conflict candidates
- source-by-source evidence inspector

### Phase 10 — optional local GraphRAG

Planned only after graph/evidence quality is measurable:

- graph + source-span retrieval
- optional Ollama-compatible local synthesis
- local sentence-transformer embeddings
- answer citations to frozen evidence IDs
- deterministic vs local-LLM vs hybrid benchmark
- no mandatory paid provider

## Release rule

A feature is not considered complete because its Python function works. The Definition of Done is:

```text
unit/invariant tests
    -> API/integration tests
    -> persistence/security tests where relevant
    -> frontend build
    -> Docker build
    -> browser E2E
    -> reproducible documentation
```

If the complete user journey cannot be executed, the feature is not finished.
