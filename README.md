# VerityGraph AI

**Evidence-grounded document, graph and retrieval intelligence where every important output can be traced back to source evidence.**

VerityGraph AI is a local-first, production-deployable research application for turning PDFs, DOCX files, text files, selected Wikipedia content and permitted public web pages into persistent evidence, explicit provenance, knowledge graphs, source comparisons, measured retrieval and bounded evidence packs.

> **Release status: 0.9.0 production-deployable beta.** The application is real and shareable today: full React UI, FastAPI backend, SQLite persistence, deterministic local NLP, graph analytics, citation topology, retrieval/evaluation, Docker, browser E2E, HTTPS production Compose, protected-demo mode, and database backup/restore. Application-level accounts/RBAC and generated Q&A are intentionally still separate hardening layers rather than being implied by the current release.

## Fastest way to run it

Requirements: Git + Docker.

```bash
git clone https://github.com/mohit231007/veritygraph-ai.git
cd veritygraph-ai
docker compose up -d --build
```

Open:

```text
App:      http://localhost:3000
API docs: http://localhost:8000/docs
```

Windows shortcut:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1
```

macOS/Linux shortcut:

```bash
chmod +x scripts/start-local.sh
./scripts/start-local.sh
```

For domain-backed HTTPS hosting, password-protected demos, LAN sharing, temporary public tunnels, upgrades, backup and restore, see **[`docs/deployment.md`](docs/deployment.md)**.

## What a user can do now

### Build a persistent research workspace

A workspace can combine:

- PDF documents;
- Word/DOCX documents;
- text files;
- selected sections from Wikipedia;
- permitted public HTTP(S) pages.

All inputs converge into one canonical source/evidence model and persist in SQLite across browser/backend restarts.

### Inspect exact provenance

VerityGraph retains source-level and span-level lineage rather than flattening everything into anonymous text.

```text
SourceDocument
  -> SourceSpan
  -> SourceReference
  -> SourceIdentifier
```

Depending on the format this can include page, section, paragraph, MediaWiki revision/section, explicit URL reference, citation marker/bibliography text, DOI, arXiv ID or validated ISBN.

### Analyse entities and relationships locally

spaCy powers deterministic local NER/dependency extraction. Relations retain exact evidence and conservative assertion qualifiers such as polarity, modality and explicit year scope.

Entity resolution is intentionally conservative and explainable. Ambiguous aliases remain separate rather than being force-merged.

### Explore an evidence graph

The analysis run projects into a NetworkX evidence graph with an interactive Cytoscape browser UI.

Available structural views include:

- directed evidence assertions;
- PageRank;
- degree/betweenness context;
- connected components;
- communities;
- graph density;
- evidence-backed connection paths.

Explicit negated and modal/future assertions remain inspectable but are excluded from established structural connectivity.

### Compare sources without pretending source IDs prove independence

Source comparison exposes:

- relation support across sources;
- evidence diversity;
- scoped contradiction candidates;
- exact content/evidence overlap review signals;
- possible derivation signals where deterministic overlap supports review.

A contradiction candidate is a review signal, not a truth verdict.

### Inspect explicit citation/reference lineage

VerityGraph preserves and resolves supported explicit references from:

- visible URLs;
- HTML links tied to retained main content;
- DOCX hyperlinks;
- PDF URI link annotations;
- selected MediaWiki citations/reference entries.

URL matches can be external, uniquely resolved to a workspace source, or ambiguous.

### Preserve DOI / arXiv / ISBN identity without overclaiming

Bibliographic identifiers have separate roles:

```text
mention
reference
source_identity
```

Two sources merely mentioning the same DOI are **not** treated as proof that either source is that DOI's work. `source_identity` is only attested from supported acquisition URLs such as DOI/arXiv work URLs.

### Explore a deterministic citation graph

A directed source-to-source citation edge is admitted only when explicit provenance uniquely resolves:

```text
SourceReference -> one workspace URL target
```

or:

```text
reference-role identifier -> one attested source_identity target
```

Shared identifier mentions alone create no citation edge. Ambiguous references remain review data instead of being forced into topology.

### Retrieve exact evidence spans

The retrieval preview uses a deterministic local BM25-style lexical ranker over persisted `SourceSpan` text.

Citation neighbors are returned separately as discovery context. Graph connectivity does not change lexical scores and does not promote a neighbor's text into ranked evidence.

### Measure retrieval instead of claiming improvement

The Retrieval Evaluation Lab accepts explicit relevant-span labels and reports:

- Recall@K;
- Precision@K;
- HitRate@K;
- Mean Reciprocal Rank;
- per-query first relevant rank and diagnostics.

Stale labels referring to spans outside the workspace fail closed instead of silently lowering metrics.

### Build a Grounded Evidence Pack

The Grounded Evidence Pack is the deterministic boundary before any future generator.

Users choose explicit budgets for:

- total excerpts;
- excerpts per source;
- characters per excerpt;
- total context characters.

The output retains exact source/span IDs and excerpt character ranges. A long span is windowed deterministically around matched query terms.

The UI can:

- inspect every allowed excerpt;
- inspect citation discovery metadata separately;
- copy a generator-ready evidence block;
- download the full pack as JSON.

**Citation-neighbor text does not enter the evidence pack unless one of that source's own spans independently matched retrieval.**

## Evidence architecture

```text
PDF / DOCX / TXT ─┐
Wikipedia ─────────┼─> SourceDocument + SourceSpan
Public web ────────┘            |
                                +-> explicit URL/citation lineage
                                +-> DOI/arXiv/ISBN lineage
                                |
                                v
                         persistent SQLite
                                |
                                v
                        Research Workspace
                         /             \
                        v               v
             immutable NLP run    citation topology
                        |               |
                        v               |
        Entity + qualified relation     |
        + exact RelationEvidence        |
                        |               |
                        v               |
                  Evidence Graph        |
                        |               |
                        +-------+-------+
                                |
                                v
                      direct span retrieval
                                |
                     +----------+----------+
                     |                     |
                     v                     v
             ranked evidence       citation context
                     |              metadata only
                     v
                evaluation
                     |
                     v
             Grounded Evidence Pack
                     |
                     v
            future grounded generator
```

The invariant is **provenance before inference**.

## Stack

| Layer | Implementation |
|---|---|
| Frontend | React + TypeScript + Vite |
| Production frontend | Nginx |
| API | FastAPI + Pydantic |
| Persistence | SQLite |
| PDF | PyMuPDF |
| DOCX | python-docx |
| Wikipedia | MediaWiki Action API |
| Public HTTP | httpx with SSRF-aware validation |
| Web extraction | Trafilatura + Beautiful Soup |
| NLP | spaCy `en_core_web_sm` |
| Graph analytics | NetworkX |
| Browser graph | Cytoscape.js |
| Retrieval | deterministic BM25-style lexical ranking |
| Backend tests | pytest + Ruff |
| Browser tests | Playwright |
| Local containers | Docker Compose |
| Production edge | Caddy + automatic HTTPS |
| CI | GitHub Actions |

No paid API is mandatory for the current core application.

## Run in developer mode

### Backend

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_sm
uvicorn app.main:app --app-dir backend --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://localhost:8000`.

## Share it with other people

### Same Wi-Fi/LAN

Run Docker locally, then share:

```text
http://YOUR-LAN-IP:3000
```

Use this only on a trusted network because there is no app-level login in 0.9.

### Temporary internet demo

After the local stack is running and `cloudflared` is installed:

```powershell
# Windows
.\scripts\share-quick.ps1
```

```bash
# macOS/Linux
sh scripts/share-quick.sh
```

This prints a temporary public HTTPS URL. It is a demo/testing path, not durable production hosting.

### Durable HTTPS deployment

Use a Linux VPS/server and a domain:

```bash
cp .env.production.example .env.production
# set VERITYGRAPH_DOMAIN in .env.production
sh scripts/deploy-prod.sh .env.production
```

Production topology:

```text
Internet -> Caddy HTTPS -> frontend Nginx -> internal FastAPI -> SQLite volume
```

Only Caddy is published publicly in `docker-compose.prod.yml`.

### Password-protected portfolio/client demo

Switch in `.env.production`:

```dotenv
VERITYGRAPH_CADDYFILE=./deploy/Caddyfile.protected
VERITYGRAPH_AUTH_USER=demo
VERITYGRAPH_AUTH_PASSWORD_HASH='CADDY_GENERATED_HASH'
```

This is a shared outer password gate, **not** multi-user RBAC.

Full instructions: [`docs/deployment.md`](docs/deployment.md).

## Backup and restore

Production ships `scripts/sqlite_backup.py` and an explicit `ops` profile. The normal API runtime remains non-root; only the one-off backup/restore service receives the host `./backups` mount.

Example live backup:

```bash
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
docker compose --env-file .env.production -f docker-compose.prod.yml --profile ops run --rm backup \
  backup \
  --source /data/veritygraph.db \
  --output /backups/veritygraph-$STAMP.db
```

The utility uses SQLite's backup API. Restore also removes stale destination WAL/SHM sidecars before rebuilding the database. Full restore instructions and the required writer stop/start sequence are in the deployment runbook.

## API

FastAPI's complete interactive schema is available at `/docs` when the backend is running.

Important route groups include:

```text
/api/v1/health
/api/v1/documents/*
/api/v1/wikipedia/*
/api/v1/web/*
/api/v1/sources/*
/api/v1/workspaces/*
/api/v1/workspaces/{id}/reference-lineage
/api/v1/workspaces/{id}/identifier-lineage
/api/v1/workspaces/{id}/citation-graph
/api/v1/workspaces/{id}/retrieval/preview
/api/v1/workspaces/{id}/retrieval/evaluate
/api/v1/workspaces/{id}/retrieval/evidence-pack
/api/v1/analyses/*
```

## QA contract

Every pull request is gated by:

1. frontend TypeScript/Vite production build;
2. Ruff over backend and operational scripts;
3. complete pytest backend regression suite using a real local spaCy model;
4. production Docker Compose syntax validation;
5. public and protected Caddy configuration validation;
6. non-root Docker stack startup;
7. full Playwright browser regression suite against React + Nginx + FastAPI + SQLite.

Run locally:

```bash
python scripts/qa.py
python scripts/qa.py --e2e
```

or:

```bash
make qa
```

## Current deployment/security boundary

0.9 is suitable for:

- a single-owner real deployment;
- a portfolio/recruiter demo;
- a client demo;
- a trusted small research team;
- a password-gated shared workspace.

It is **not yet an untrusted multi-tenant SaaS**. Before that step, add:

- application login/identity;
- workspace ownership and RBAC;
- quotas/rate limits/abuse controls;
- identity-aware audit logging;
- secrets management and production monitoring;
- a database architecture designed for multiple application instances.

See [`docs/deployment.md`](docs/deployment.md) and [`docs/adr/0022-production-deployment-boundary.md`](docs/adr/0022-production-deployment-boundary.md).

## Repository map

```text
backend/              FastAPI, domain/services, SQLite repositories, NLP/graph logic, tests
frontend/             React/TypeScript evidence intelligence UI
e2e/                  Playwright full-browser journeys
deploy/               Caddy public/protected production edge configs
docs/                  architecture, runbook, data model, QA and ADRs
scripts/               QA, launch, sharing and SQLite backup utilities
.github/workflows/     mandatory quality gate
```

## Roadmap after 0.9

The next high-value layers are deliberately measurable rather than demo-only:

1. application identity, workspace ownership and RBAC;
2. optional grounded answer generation consuming only `GroundedEvidencePack`;
3. claim-to-evidence validation for generated answers;
4. semantic/hybrid retrieval evaluated against the existing labelled benchmark;
5. persistent evaluation datasets and regression dashboards;
6. PostgreSQL/managed-database path for multi-user deployments;
7. optional Neo4j adapter for larger graph workloads;
8. optional local embedding/generation adapters.

## Architecture decisions

Start with:

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/data-model.md`](docs/data-model.md)
- [`docs/qa.md`](docs/qa.md)
- [`docs/adr/0021-grounded-evidence-pack.md`](docs/adr/0021-grounded-evidence-pack.md)
- [`docs/adr/0022-production-deployment-boundary.md`](docs/adr/0022-production-deployment-boundary.md)

## License

MIT.
