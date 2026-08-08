# ADR 0003: Use the official MediaWiki API with a deterministic QA provider

- Status: Accepted
- Date: 2026-08-09

## Context

VerityGraph's public-knowledge workflow needs search, article-outline discovery and selected-section ingestion from Wikipedia. Scraping search-engine result pages or Wikipedia presentation HTML would couple the product to unstable UI markup and make automated tests depend on public-network availability.

MediaWiki exposes an official Action API for search and page parsing. The current API documents `action=query&list=search` for full-text search and `action=parse&prop=tocdata` for table-of-contents metadata. `prop=sections` is deprecated, so VerityGraph uses `tocdata` for new code.

## Decision

The default Wikipedia adapter uses the official English Wikipedia MediaWiki Action API.

- Search: `action=query&list=search`.
- Outline: `action=parse&prop=tocdata|revid|displaytitle`.
- Selected content: `action=parse&prop=text&section=<index>`.
- Imported content is normalized into the same `SourceDocument` / `SourceSpan` contract as uploaded documents.
- Source metadata records Wikipedia page ID and revision ID.
- Public source URL is retained on `SourceDocument.url`.
- Search snippets and selected-section HTML are converted into normalized readable text before downstream NLP.

## Deterministic QA

CI must not fail because Wikipedia is temporarily unavailable or an article changes.

VerityGraph therefore exposes the provider interface through two implementations:

1. `MediaWikiWikipediaProvider` — live/default adapter.
2. `FixtureWikipediaProvider` — explicit deterministic adapter for browser E2E.

Backend protocol tests additionally use `httpx.MockTransport` to validate our interpretation of MediaWiki search, TOCData and parsed-section response shapes without network access.

The fixture adapter is never selected by default. It must be enabled with:

```text
VERITYGRAPH_WIKIPEDIA_PROVIDER=fixture
```

GitHub Actions and `python scripts/qa.py --e2e` set this only for deterministic tests.

## Why not mock the frontend only?

A frontend-only network mock would verify UI state but would skip FastAPI routing, provider selection, section normalization, source hashing, repository persistence and source-span construction. The fixture provider keeps the browser journey full-stack while replacing only the unstable external boundary.

## Consequences

### Positive

- zero API-key and zero paid-search dependency for Wikipedia discovery;
- stable browser E2E;
- official rather than presentation-layer integration;
- real revision provenance;
- provider abstraction can later support additional MediaWiki instances or public knowledge sources.

### Trade-offs

- live results can still change between user sessions;
- section indices are revision-specific and are consumed immediately rather than treated as durable identifiers;
- complex page HTML requires normalization and may not preserve every visual/table nuance;
- Wikimedia availability and usage policies remain external operational dependencies for live mode.
