# VerityGraph AI

**Evidence-grounded document and web intelligence. Every insight traceable to its source.**

VerityGraph AI is a local-first, zero-mandatory-API-cost platform that transforms PDFs, Word documents, text files, Wikipedia pages, and permitted public web content into traceable knowledge graphs, relationship intelligence, graph analytics, and source-grounded Q&A.

> Status: **Phase 1 — document provenance vertical slice**. The product foundation is green, and PDF/DOCX/TXT ingestion now normalizes uploaded content into canonical `SourceDocument` and `SourceSpan` records before any NLP runs.

## Why this project exists

Most knowledge-graph demos stop at `text -> entities -> edges`. VerityGraph is designed around a stronger invariant:

```text
Relation -> Evidence -> SourceSpan -> SourceDocument
```

Generated answers will preserve the evidence IDs and analysis-run version that produced them. Users will be able to rate an answer, explain what needs improvement, regenerate against the same frozen evidence, compare versions, and keep/export the preferred response.

## What works now

### Document intelligence

Upload:

- PDF
- DOCX
- TXT

The ingestion layer performs extension/MIME validation, filename sanitization, bounded reads, SHA-256 hashing, format-specific parsing and provenance construction.

Current provenance behavior:

- **PDF:** one normalized evidence span per readable page.
- **DOCX:** paragraph spans plus table-row spans. Page numbers are not guessed because DOCX pagination depends on rendering.
- **TXT:** blank-line-delimited paragraph spans with synthetic page 1.
- **Scanned PDFs:** fail clearly for now instead of silently producing empty evidence; OCR is a future adapter.

The React interface can upload a source through the real FastAPI service and render filename, format, hash, page/paragraph location, normalized character offsets and extracted evidence text.

## Product pillars

- **Two ingestion paths, one canonical model** — upload documents or discover public content; both normalize into the same source representation.
- **Evidence first** — graph edges and generated insights are traceable to supporting spans, pages, sections, files, and URLs.
- **Multi-source intelligence** — combine documents, Wikipedia, and permitted public URLs in one workspace.
- **Insight Studio** — rate, critique, improve, compare, copy, download, and later share reproducible insight versions.
- **Explainable confidence** — distinguish source-derived facts, graph-computed insights, and generated synthesis.
- **Local-first and free by default** — no paid API is required for the core product.
- **Quality as a feature** — unit, integration, provenance, API, regression, build, container, and Playwright E2E checks converge into one QA command.

## Free/open stack

| Layer | Default |
|---|---|
| Frontend | React + TypeScript + Vite |
| API | FastAPI |
| NLP | spaCy |
| PDF | PyMuPDF |
| DOCX | python-docx |
| Web extraction | Trafilatura |
| Wikipedia | MediaWiki API |
| Search | Optional self-hosted SearXNG adapter |
| Graph | NetworkX; Neo4j Community adapter later |
| Metadata | SQLite; PostgreSQL local adapter later |
| Local generation | Optional Ollama-compatible models |
| Embeddings | sentence-transformers |
| Backend QA | pytest + Ruff |
| Frontend QA | TypeScript build |
| Browser E2E | Playwright |
| Containers | Docker Compose |
| CI | GitHub Actions |

## Current architecture

```text
Browser
  |
  | upload PDF / DOCX / TXT
  v
React / Vite
  |
  | multipart/form-data
  v
FastAPI
  |
  +--> validation + upload limit
  |
  +--> PDF / DOCX / TXT parser
  |
  v
SourceDocument + SourceSpan[]
  |
  +--> in-memory repository (v0.2)
  |
  +--> Phase 2+: NLP -> relations -> evidence graph -> insights
```

The important architectural rule is **provenance before NLP**. Downstream components will receive source spans rather than anonymous raw strings.

## API contracts available now

```text
GET  /api/v1/health
POST /api/v1/documents/upload
GET  /api/v1/documents/{source_id}
```

Interactive API documentation is available at `/docs` when the backend is running.

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

Complete E2E gate:

```bash
python scripts/qa.py --e2e
```

If `make` is available:

```bash
make qa
```

The browser E2E suite now verifies both the API health contract and a real TXT upload from browser -> Nginx -> FastAPI -> parser -> provenance -> browser preview.

## Repository map

```text
backend/              FastAPI application, domain model, ingestion and tests
frontend/             React/TypeScript interface
e2e/                  Playwright browser journeys
docs/                  architecture, provenance model, ADRs and QA contract
scripts/               cross-platform developer automation
.github/workflows/     CI quality gates
```

## Roadmap

1. ✅ Canonical `SourceDocument` / `SourceSpan` / provenance models.
2. ✅ PDF, DOCX, and TXT ingestion with page/paragraph lineage.
3. Wikipedia search, article preview, and section selection.
4. Secure public-URL ingestion with SSRF protection.
5. SQLite source/workspace persistence.
6. spaCy NER and dependency-based relation extraction baseline.
7. Entity resolution and alias handling.
8. Evidence graph + NetworkX analytics.
9. Insight Studio feedback/versioning/export workflow.
10. Multi-source comparison and conflict candidates.
11. Optional local GraphRAG and answer-improvement engine.
12. Golden NLP evaluation sets and measured precision/recall/F1.
13. Neo4j Community adapter and larger-corpus workflows.

See `docs/architecture.md`, `docs/data-model.md`, `docs/qa.md`, and the ADRs for design rationale.

## License

MIT.
