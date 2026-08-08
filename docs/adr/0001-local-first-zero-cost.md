# ADR 0001: Local-first, zero-mandatory-cost architecture

- **Status:** Accepted
- **Date:** 2026-08-09

## Context

VerityGraph must be useful as a portfolio project, a reproducible engineering system, and a practical research tool without forcing users to buy API credits or subscribe to hosted infrastructure.

## Decision

The default product path must require no paid API or proprietary hosted dependency.

Defaults:

- FastAPI and React for application boundaries.
- SQLite and NetworkX for local persistence/graphs.
- spaCy for baseline linguistic extraction.
- MediaWiki APIs for Wikipedia discovery/content.
- direct permitted URL ingestion; self-hosted SearXNG may be added for general search.
- local Ollama-compatible models and sentence-transformers only as optional generative/semantic enrichments.
- Docker Compose for reproducible local services.

Paid providers may be added only behind optional adapters. Core ingestion, extraction, graph analytics, evidence browsing, feedback capture, and exports must remain functional without them.

## Consequences

### Positive

- reproducible demo and QA environment;
- no secret/API-key requirement for the basic product;
- useful offline/local privacy story for uploaded documents;
- provider abstractions can still support enterprise integrations later.

### Trade-offs

- local generative performance depends on user hardware;
- general web search is harder without an external index;
- high-throughput production deployments will need configurable persistent services.

These trade-offs are explicit rather than hidden behind an apparently free hosted API tier.
