# VerityGraph AI

**Evidence-grounded document and web intelligence. Every insight traceable to its source.**

VerityGraph AI is a local-first, zero-mandatory-API-cost platform that transforms PDFs, Word documents, text files, Wikipedia pages, and permitted public web pages into persistent, traceable evidence that can power knowledge graphs, relationship intelligence, graph analytics, and source-grounded Q&A.

> Status: **Phase 4 — persistent multi-source research workspaces**. PDF/DOCX/TXT uploads, Wikipedia discovery, and secure public-URL imports converge into one canonical provenance model and are now persisted locally in SQLite so research collections survive browser and backend restarts.

## Why this project exists

Most knowledge-graph demos stop at `text -> entities -> edges`. VerityGraph is being built around a stronger invariant:

```text
Relation -> Evidence -> SourceSpan -> SourceDocument
```

The same lineage will extend into generated answers and response versions so users can inspect why a claim exists, rate it, explain what is weak, improve the answer against frozen evidence, compare versions, and keep/export the preferred response.

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

### 4. Persistent multi-source workspaces

Canonical sources and evidence spans are now stored in **SQLite by default**. Users can create named research workspaces and combine any mixture of:

- uploaded documents;
- Wikipedia selections;
- permitted public URLs.

Workspace membership is separate from source identity:

- adding the same source twice is idempotent;
- removing a source from a workspace does not delete the canonical source;
- deleting a workspace does not delete its source records;
- deleting a source automatically removes orphan workspace membership through foreign-key cascades.

The React interface lets users create/select a workspace, add the current analysed source, inspect the collection, remove membership, and reload the browser while the workspace remains available.

Docker persists the database in a named local volume at `/data/veritygraph.db`. The backend container runs as a dedicated non-root `veritygraph` user.

## One canonical evidence architecture

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
                     SQLite store
                           |
                           v
                Research Workspace(s)
                           |
                           v
             Phase 5+: NLP / relations
                           |
                           v
                evidence-grounded graph
```

The architectural rule remains **provenance before NLP**. Downstream components consume durable `SourceSpan` identities rather than anonymous strings.

## Product pillars

- **Different inputs, one canonical model** — documents and public knowledge share one source/evidence contract.
- **Evidence first** — future graph edges and generated insights remain traceable to spans, pages, sections, revisions, files, and URLs.
- **Persistent multi-source intelligence** — heterogeneous evidence can be grouped into reusable local research workspaces.
- **Insight Studio** — rate, critique, improve, compare, copy, download, and later share reproducible answer versions.
- **Explainable confidence** — separate source-derived facts, graph-computed insights, and generated synthesis.
- **Local-first and free by default** — no paid API or hosted database is required for the core product.
- **Quality as a feature** — unit, security, protocol, persistence, provenance, API, container, and browser E2E tests evolve with every feature.

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
| Persistence/workspaces | SQLite |
| NLP (next) | spaCy |
| Graph (next) | NetworkX |
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

GET  /api/v1/sources
GET  /api/v1/sources/{source_id}

POST   /api/v1/workspaces
GET    /api/v1/workspaces
GET    /api/v1/workspaces/{workspace_id}
PUT    /api/v1/workspaces/{workspace_id}/sources/{source_id}
DELETE /api/v1/workspaces/{workspace_id}/sources/{source_id}
DELETE /api/v1/workspaces/{workspace_id}
```

FastAPI interactive documentation is available at `/docs` when the backend is running.

## Quality strategy

VerityGraph tests each external/storage boundary separately and then verifies the whole user journey:

- real in-memory PDF/DOCX fixtures exercise document parsing;
- MediaWiki protocol tests use `httpx.MockTransport` to validate search/TOC/section-response handling without public-network dependency;
- public-web security tests use mocked DNS and HTTP transport to prove unsafe targets, redirects, MIME types, and oversized bodies are rejected;
- SQLite tests write data, recreate repository objects against the same database file, and verify source/workspace restoration;
- deterministic Wikipedia/Web fixture providers replace only external network boundaries during browser E2E;
- Playwright still drives the real React UI, Nginx proxy, FastAPI routes, SQLite repository, normalization, and provenance preview.

Current mandatory browser regressions:

```text
Browser -> TXT upload -> parser -> SQLite -> provenance -> preview
Browser -> Wikipedia search -> outline -> section import -> SQLite -> provenance -> preview
Browser -> public URL -> safe import -> extraction -> SQLite -> provenance -> preview
Browser -> create workspace -> add source -> reload -> source still in workspace
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

By default, local data is stored at `data/veritygraph.db`. Override with `VERITYGRAPH_DATABASE_PATH`.

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

Docker persists application data in the named `veritygraph_data` volume. Use `docker compose down` to stop the stack without deleting data. Removing the volume is intentionally a separate operation.

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
backend/              FastAPI, domain models, safe ingestion, SQLite repositories, tests
frontend/             React/TypeScript Source Studio, workspaces, shared provenance UI
e2e/                  Playwright full-browser journeys
docs/                  architecture, data model, security/persistence ADRs, QA contract
scripts/               cross-platform developer automation
.github/workflows/     CI quality gates
```

## Roadmap

1. ✅ Production foundation + browser/API quality gate.
2. ✅ Canonical `SourceDocument` / `SourceSpan` provenance model.
3. ✅ PDF, DOCX, TXT ingestion.
4. ✅ Wikipedia search, section selection, revision provenance.
5. ✅ SSRF-aware public URL ingestion + main-content extraction.
6. ✅ SQLite source persistence + multi-source research workspaces.
7. **spaCy entity extraction + evidence-linked relation extraction + analysis runs.**
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
