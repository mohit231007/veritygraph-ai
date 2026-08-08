# VerityGraph AI

**Evidence-grounded document and web intelligence. Every insight traceable to its source.**

VerityGraph AI is a local-first, zero-mandatory-API-cost platform that transforms PDFs, Word documents, text files, Wikipedia pages, and permitted public web content into traceable knowledge graphs, relationship intelligence, graph analytics, and source-grounded Q&A.

> Status: **Phase 2 — dual-source ingestion**. PDF/DOCX/TXT uploads and Wikipedia discovery now converge into the same canonical `SourceDocument` / `SourceSpan` provenance model before any NLP runs.

## Why this project exists

Most knowledge-graph demos stop at `text -> entities -> edges`. VerityGraph is designed around a stronger invariant:

```text
Relation -> Evidence -> SourceSpan -> SourceDocument
```

Generated answers will preserve the evidence IDs and analysis-run version that produced them. Users will be able to rate an answer, explain what needs improvement, regenerate against the same frozen evidence, compare versions, and keep/export the preferred response.

## What works now

### 1. Document intelligence

Upload:

- PDF
- DOCX
- TXT

The ingestion layer performs extension/MIME validation, filename sanitization, bounded reads, SHA-256 hashing, format-specific parsing and provenance construction.

Current provenance behavior:

- **PDF:** one normalized evidence span per readable page.
- **DOCX:** paragraph spans plus table-row spans. Page numbers are not guessed because DOCX pagination depends on rendering.
- **TXT:** blank-line-delimited paragraph spans with synthetic page 1.
- **Scanned PDFs:** fail clearly instead of silently producing empty evidence; OCR is a future adapter.

### 2. Wikipedia intelligence

The Source Studio can now:

1. search Wikipedia through the official MediaWiki Action API;
2. inspect an article outline;
3. select only the sections relevant to the analysis;
4. import those sections into canonical evidence spans;
5. retain public source URL, Wikipedia page ID, revision ID, section heading and paragraph provenance.

The implementation uses current `tocdata` table-of-contents metadata instead of building new code on the deprecated `prop=sections` response.

Normal runtime defaults to live English Wikipedia and requires no API key. Automated tests use a deterministic fixture provider through the same interface, so CI never depends on public-network availability or article drift.

## One canonical source contract

```text
                        +--------------------+
                        | Upload PDF/DOCX/TXT|
                        +----------+---------+
                                   |
                                   v
+-------------------+       +---------------+
| Wikipedia search  +------>| SourceDocument|
| + section chooser |       +-------+-------+
+-------------------+               |
                                    v
                              SourceSpan[]
                                    |
                    +---------------+----------------+
                    |                                |
                    v                                v
              NLP / entities                  Evidence / citations
                    |                                |
                    +---------------+----------------+
                                    v
                              Knowledge graph
```

The important architectural rule is **provenance before NLP**. Downstream components receive source spans rather than anonymous raw strings.

## Product pillars

- **Different inputs, one canonical model** — uploaded documents and public knowledge share one source/evidence contract.
- **Evidence first** — graph edges and generated insights are traceable to supporting spans, pages, sections, files, revisions, and URLs.
- **Multi-source intelligence** — combine documents, Wikipedia, and permitted public URLs in one workspace.
- **Insight Studio** — rate, critique, improve, compare, copy, download, and later share reproducible insight versions.
- **Explainable confidence** — distinguish source-derived facts, graph-computed insights, and generated synthesis.
- **Local-first and free by default** — no paid API is required for the core product.
- **Quality as a feature** — unit, protocol, integration, provenance, API, build, container, and browser E2E checks converge into one QA command.

## Free/open stack

| Layer | Default |
|---|---|
| Frontend | React + TypeScript + Vite |
| API | FastAPI |
| NLP | spaCy |
| PDF | PyMuPDF |
| DOCX | python-docx |
| Wikipedia | Official MediaWiki Action API |
| HTML normalization | Beautiful Soup |
| Future web extraction | Trafilatura |
| Future general search | Optional self-hosted SearXNG adapter |
| Graph | NetworkX; Neo4j Community adapter later |
| Metadata | SQLite next; PostgreSQL local adapter later |
| Local generation | Optional Ollama-compatible models |
| Embeddings | sentence-transformers |
| Backend QA | pytest + Ruff |
| Frontend QA | TypeScript build |
| Browser E2E | Playwright |
| Containers | Docker Compose |
| CI | GitHub Actions |

## API contracts available now

```text
GET  /api/v1/health

POST /api/v1/documents/upload
GET  /api/v1/documents/{source_id}

GET  /api/v1/wikipedia/search?q=<topic>
GET  /api/v1/wikipedia/pages/{page_id}/outline
POST /api/v1/wikipedia/import
```

Interactive API documentation is available at `/docs` when the backend is running.

## Quality strategy

There are deliberately different test boundaries:

- parser/API tests generate real in-memory PDF and DOCX fixtures;
- Wikipedia API tests use the deterministic provider;
- MediaWiki protocol tests use `httpx.MockTransport` to verify official search, TOC and parsed-section response handling without network access;
- Playwright runs the complete browser -> Nginx -> FastAPI -> provider/parser -> canonical provenance -> browser journey;
- CI uses `VERITYGRAPH_WIKIPEDIA_PROVIDER=fixture` only for E2E. Normal runtime remains live.

Current mandatory browser regressions:

```text
Browser -> upload TXT -> FastAPI -> parser -> provenance -> preview
Browser -> Wikipedia search -> outline -> select sections -> import -> provenance -> preview
```

## Run locally

### 1. Backend

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --app-dir backend --reload
```

API health: `http://localhost:8000/api/v1/health`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

### 3. Full stack with Docker

```bash
docker compose up --build
```

Frontend: `http://localhost:3000`

### 4. QA

Fast developer checks:

```bash
python scripts/qa.py
```

Complete deterministic E2E gate:

```bash
python scripts/qa.py --e2e
```

If `make` is available:

```bash
make qa
```

`--e2e` automatically switches the Wikipedia boundary to its deterministic fixture only for the test run, then restores the previous environment setting.

## Repository map

```text
backend/              FastAPI, domain contracts, ingestion/providers and tests
frontend/             React/TypeScript Source Studio and provenance UI
e2e/                  Playwright full-browser journeys
docs/                  architecture, data model, ADRs and QA contract
scripts/               cross-platform developer automation
.github/workflows/     CI quality gates
```

## Roadmap

1. ✅ Production foundation + browser/API quality gate.
2. ✅ Canonical `SourceDocument` / `SourceSpan` provenance model.
3. ✅ PDF, DOCX, and TXT ingestion with page/paragraph lineage.
4. ✅ Wikipedia search, article preview, section selection, revision provenance.
5. Secure public-URL ingestion with SSRF protection.
6. SQLite source/workspace persistence.
7. spaCy NER and dependency-based relation extraction baseline.
8. Entity resolution and alias handling.
9. Evidence graph + NetworkX analytics.
10. Insight Studio feedback/versioning/copy/download workflow.
11. Multi-source comparison and conflict candidates.
12. Optional local GraphRAG and answer-improvement engine.
13. Golden NLP evaluation sets and measured precision/recall/F1.
14. Neo4j Community adapter and larger-corpus workflows.

See `docs/architecture.md`, `docs/data-model.md`, `docs/qa.md`, and `docs/adr/` for the design rationale.

## License

MIT.
