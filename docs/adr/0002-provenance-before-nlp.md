# ADR 0002: Create provenance before NLP

- Status: Accepted
- Date: 2026-08-09

## Context

VerityGraph will extract entities, relationships and generated insights from heterogeneous sources. If source text is flattened into anonymous strings first, evidence tracing has to be reconstructed later and can become inaccurate or impossible.

## Decision

Every source is normalized into `SourceDocument` plus `SourceSpan[]` before any NLP component runs.

Downstream components will reference stable `source_id` and `span_id` values. They must not invent their own untraceable source text representation.

The first supported document adapters are PDF, DOCX and TXT. Wikipedia and permitted public URLs will implement the same canonical contract.

## Consequences

### Positive

- Every future graph edge can carry exact source evidence.
- Generated claims can cite one or more source spans.
- Response regeneration can freeze evidence while changing only synthesis.
- Refreshing source material can create a new analysis run without mutating previous evidence.
- Multi-source agreement/conflict analysis becomes possible.
- Evaluation can test provenance integrity independently of NLP quality.

### Trade-offs

- Ingestion code is more structured than simply returning a large text string.
- Character offsets are defined over normalized extracted text rather than binary file offsets.
- DOCX page numbers are intentionally unavailable unless a rendering-aware adapter is introduced.
- Scanned PDFs need an OCR adapter and are not silently treated as empty text.

## Rejected alternative

**Flatten every source to plain text and add citations later.** Rejected because it makes evidence lineage fragile and encourages unsupported graph/LLM claims.
