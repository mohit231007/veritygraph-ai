# VerityGraph AI

**Evidence-grounded document and web intelligence. Every insight traceable to its source.**

VerityGraph AI is a local-first, zero-mandatory-API-cost platform that transforms PDFs, Word documents, text files, Wikipedia pages, and permitted public web content into traceable knowledge graphs, relationship intelligence, graph analytics, and source-grounded Q&A.

> Status: **Phase 0 — foundation**. The repository currently establishes the production shell, API/UI health contract, Docker workflow, CI, and browser E2E quality gate. The NLP and ingestion layers are the next milestones.

## Why this project exists

Most knowledge-graph demos stop at `text -> entities -> edges`. VerityGraph is designed around a stronger invariant:

```text
Relation -> Evidence -> SourceSpan -> SourceDocument
```

Generated answers will preserve the evidence IDs and analysis-run version that produced them. Users will be able to rate an answer, explain what needs improvement, regenerate against the same frozen evidence, compare versions, and keep/export the preferred response.

## Product pillars

- **Two ingestion paths, one canonical model** — upload documents or discover public content; both normalize into the same source representation.
- **Evidence first** — graph edges and generated insights are traceable to supporting spans, pages, sections, files, and URLs.
- **Multi-source intelligence** — combine documents, Wikipedia, and permitted public URLs in one workspace.
- **Insight Studio** — rate, critique, improve, compare, copy, download, and later share reproducible insight versions.
- **Explainable confidence** — distinguish source-derived facts, graph-computed insights, and generated synthesis.
- **Local-first and free by default** — no paid API is required for the core product.
- **Quality as a feature** — unit, integration, provenance, API, regression, build, container, and Playwright E2E checks converge into one QA command.

## Planned free/open stack

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

## Phase 0 architecture

```text
Browser
  |
  v
React / Vite
  |  GET /api/v1/health
  v
FastAPI
  |
  +--> Phase 1+: ingestion -> source spans -> NLP -> evidence graph
```

The first contract is intentionally small: the real browser must be able to reach the real API. Every feature added after this point inherits a green end-to-end baseline.

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

## Repository map

```text
backend/              FastAPI application and tests
frontend/             React/TypeScript interface
e2e/                  Playwright browser journeys
docs/                  architecture, ADRs, and QA contract
scripts/               cross-platform developer automation
.github/workflows/     CI quality gates
```

## Roadmap

1. Canonical `SourceDocument` / `SourceSpan` / provenance models.
2. PDF, DOCX, and TXT ingestion with page/paragraph lineage.
3. Wikipedia search, article preview, and section selection.
4. Secure public-URL ingestion with SSRF protection.
5. spaCy NER and dependency-based relation extraction baseline.
6. Entity resolution and alias handling.
7. Evidence graph + NetworkX analytics.
8. Insight Studio feedback/versioning/export workflow.
9. Multi-source comparison and conflict candidates.
10. Optional local GraphRAG and answer-improvement engine.
11. Golden NLP evaluation sets and measured precision/recall/F1.
12. Neo4j Community adapter and larger-corpus workflows.

See `docs/architecture.md`, `docs/qa.md`, and the ADRs for design rationale.

## License

MIT.
