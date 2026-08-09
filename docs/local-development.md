# Local development

VerityGraph is designed to run without paid APIs or hosted infrastructure.

## Python environment

Use Python 3.12.

```bash
python -m venv .venv
```

Activate the environment, then install the backend, development tools, and the pinned free local spaCy English model:

```bash
pip install -e ".[dev,nlp]"
```

The `nlp` extra installs `en_core_web_sm` from Explosion's official spaCy model release. The backend Docker image installs the same extra so local container E2E exercises the same model used by backend tests.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to the local FastAPI backend.

## Backend

From the repository root:

```bash
uvicorn app.main:app --app-dir backend --reload
```

Default local state is persisted in:

```text
data/veritygraph.db
```

Use `VERITYGRAPH_DATABASE_PATH` to point development or tests at another SQLite file.

## External-source modes

Normal local runtime defaults to live public providers:

```text
VERITYGRAPH_WIKIPEDIA_PROVIDER=live
VERITYGRAPH_WEB_PROVIDER=live
```

Deterministic fixture providers exist only to make E2E independent from public-network availability:

```text
VERITYGRAPH_WIKIPEDIA_PROVIDER=fixture
VERITYGRAPH_WEB_PROVIDER=fixture
```

Do not use fixture providers to evaluate live-source quality.

## NLP settings

```text
VERITYGRAPH_NLP_MODEL=en_core_web_sm
VERITYGRAPH_NLP_BATCH_SIZE=64
```

`en_core_web_sm` is the zero-cost baseline. A future NLP-engine interface can expose larger spaCy/local-model options without changing the persisted analysis contract.

## Fast QA

After installing `.[dev,nlp]`:

```bash
python scripts/qa.py
```

This runs:

1. Ruff;
2. backend pytest, including the real spaCy model;
3. frontend install/build.

## Full E2E QA

Docker must be available:

```bash
python scripts/qa.py --e2e
```

The QA runner uses its own Docker Compose project and disposable SQLite volume, so it cannot read or overwrite the normal development database/volume.

The browser suite currently covers:

- API health;
- document upload and provenance;
- Wikipedia search/section import and provenance;
- secure public URL import and provenance;
- SQLite workspace persistence across reload;
- local NLP analysis, relation evidence, and persisted analysis restoration.

## Docker application runtime

```bash
docker compose up --build
```

The normal Docker stack uses a persistent named `veritygraph_data` volume. Stopping the stack with `docker compose down` retains data.

## Important analysis semantics

The current relation `extraction_score` is a deterministic rule-strength score. It is not a calibrated factual probability. See `docs/analysis.md` and ADR 0006 before changing how the UI labels this field.
