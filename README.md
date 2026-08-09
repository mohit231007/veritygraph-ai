# VerityGraph AI

**Evidence-grounded document and web intelligence. Every insight traceable to its source.**

VerityGraph AI is a local-first, zero-mandatory-API-cost platform that transforms PDFs, Word documents, text files, Wikipedia pages, and permitted public web pages into canonical evidence that can later power knowledge graphs, relationship intelligence, graph analytics, and source-grounded Q&A.

> Status: **Phase 3 — complete source-ingestion foundation**. PDF/DOCX/TXT uploads, Wikipedia discovery, and secure public-URL imports now converge into the same `SourceDocument` / `SourceSpan` provenance model before NLP.

## Why this project exists

Most knowledge-graph demos stop at `text -> entities -> edges`. VerityGraph is being built around a stronger invariant:

```text
Relation -> Evidence -> SourceSpan -> SourceDocument
```

The same lineage will later extend into generated answers and response versions so users can inspect why a claim exists, rate it, explain what is weak, improve the answer against frozen evidence, compare versions, and keep/export the preferred response.

## What works now

### 1. Document intelligence

Upload:

- PDF
- DOCX
- TXT

The document boundary performs extension/MIME validation, safe-basename normalization, bounded reads, SHA-256 hashing, format-specific parsing, and provenance construction.

- **PDF:** readable page-level spans via PyMuPDF.
- **DOCX:** paragraph spans plus table-row spans. Page numbers are not invented because DOCX pagination depends on rendering.
- **TXT:** blank-line paragraph spans with UTF-8/UTF-8-SIG and CP1252 fallback; synthetic page 1.
- **Scanned PDFs:** fail clearly until an OCR adapter lands.

### 2. Wikipedia intelligence

The Source Studio can:

1. search Wikipedia through the official MediaWiki Action API;
2. inspect the article outline;
3. select only relevant sections;
4. import selected sections into canonical evidence spans;
5. retain public URL, page ID, revision ID, section heading, and paragraph provenance.

Normal runtime uses live English Wikipedia without an API key. Deterministic tests replace only the external provider boundary.

### 3. Secure public URL intelligence

Paste a permitted public HTTP(S) page and VerityGraph will:

1. validate scheme, credentials, hostname, port, and resolved IP addresses;
2. reject private/loopback/link-local/reserved/non-global targets;
3. manually follow and revalidate redirects;
4. enforce time, redirect, content-type, and body-size limits;
5. fetch only HTML/XHTML/TXT;
6. pass already-approved bytes to Trafilatura for main-content extraction;
7. create canonical evidence spans and retain requested/final URL plus transport provenance.

Public URL ingestion does **not** support authentication/paywall/access-control bypasses. Application-level SSRF checks also do not replace production network egress restrictions; see `docs/adr/0004-public-url-ingestion-security-boundary.md`.

## One canonical source contract

```text
+----------------------+       +----------------------+
| PDF / DOCX / TXT     |       | Wikipedia discovery  |
+----------+-----------+       +-----------+----------+
           |                               |
           +---------------+---------------+
                           |
                           v
                  +------------------+
                  | SourceDocument   |
                  +--------+---------+
                           |
                           v
                    SourceSpan[]
                           ^
                           |
                 +---------+----------+
                 | Secure public URL  |
                 +--------------------+
                           |
                           v
            Phase 4+: NLP / entities / relations
                           |
                           v
                evidence-grounded graph
```

The architectural rule is **provenance before NLP**. Downstream components consume `SourceSpan` objects rather than anonymous strings.

## Product pillars

- **Different inputs, one canonical model** — documents and public knowledge share one source/evidence contract.
- **Evidence first** — future graph edges and generated insights remain traceable to spans, pages, sections, revisions, files, and URLs.
- **Multi-source intelligence** — combine heterogeneous sources inside reusable research workspaces.
- **Insight Studio** — rate, critique, improve, compare, copy, download, and later share reproducible answer versions.
- **Explainable confidence** — separate source-derived facts, graph-computed insights, and generated synthesis.
- **Local-first and free by default** — no paid API is required for the core product.
- **Quality as a feature** — unit, security, protocol, provenance, API, build, container, and browser E2E tests evolve with every feature.

## Free/open stack

| Layer | Default |
|---|---|
| Frontend | React + TypeScript + Vite |
| API | FastAPI |
| PDF | PyMuPDF |
| DOCX | python-docx |
| Wikipedia | Official MediaWiki Action API |
| Public HTTP | httpx with VerityGraph validation |
| Main web content | Trafilatura |
| HTML normalization | Beautiful Soup |
| NLP (next) | spaCy |
| Graph (next) | NetworkX |
| Metadata/workspaces (next) | SQLite |
| Optional larger graph | Neo4j Community |
| Optional local generation | Ollama-compatible models |
| Optional local embeddings | sentence-transformers |
| Backend QA | pytest + Ruff |
| Frontend QA | TypeScript/Vite build |
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

POST /api/v1/web/import
```

FastAPI interactive documentation is available at `/docs` when the backend is running.

## Quality strategy

VerityGraph tests each external boundary separately and then verifies the whole user journey:

- real in-memory PDF/DOCX fixtures exercise document parsing;
- MediaWiki protocol tests use `httpx.MockTransport` to validate search/TOC/section-response handling without public-network dependency;
- public-web security tests use mocked DNS and HTTP transport to prove unsafe targets, redirects, MIME types, and oversized bodies are rejected;
- deterministic Wikipedia/Web fixture providers replace only external network boundaries during browser E2E;
- Playwright still drives the real React UI, Nginx proxy, FastAPI routes, normalization, repository, and provenance preview.

Current mandatory browser regressions:

```text
Browser -> TXT upload -> parser -> provenance -> preview
Browser -> Wikipedia search -> outline -> section import -> provenance -> preview
Browser -> public URL -> safe import -> extraction -> provenance -> preview
```

## Run locally

### Backend

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --app-dir backend --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Full stack

```bash
docker compose up --build
```

Frontend: `http://localhost:3000`

### QA

Fast checks:

```bash
python scripts/qa.py
```

Full deterministic browser gate:

```bash
python scripts/qa.py --e2e
```

or, where `make` is available:

```bash
make qa
```

The E2E command temporarily selects deterministic Wikipedia and web fixtures and restores the caller's previous environment afterwards. Normal runtime defaults to live providers.

## Repository map

```text
backend/              FastAPI, domain models, safe ingestion/providers, repositories, tests
frontend/             React/TypeScript Source Studio and shared provenance UI
e2e/                  Playwright full-browser journeys
docs/                  architecture, data model, security decisions, ADRs, QA contract
scripts/               cross-platform developer automation
.github/workflows/     CI quality gates
```

## Roadmap

1. ✅ Production foundation + browser/API quality gate.
2. ✅ Canonical `SourceDocument` / `SourceSpan` provenance model.
3. ✅ PDF, DOCX, TXT ingestion.
4. ✅ Wikipedia search, section selection, revision provenance.
5. ✅ SSRF-aware public URL ingestion + main-content extraction.
6. **SQLite workspaces and persistent source collections.**
7. spaCy NER and dependency-based relation extraction baseline.
8. Entity resolution and alias handling.
9. Evidence graph + NetworkX analytics.
10. Insight Studio feedback/versioning/copy/download workflow.
11. Multi-source agreement/conflict intelligence.
12. Optional local GraphRAG and answer-improvement engine.
13. Golden NLP evaluation sets with measured precision/recall/F1.
14. Neo4j Community adapter and larger-corpus workflows.

See `docs/architecture.md`, `docs/data-model.md`, `docs/qa.md`, and `docs/adr/` for design rationale.

## License

MIT.
