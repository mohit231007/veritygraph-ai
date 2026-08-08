# Canonical source and provenance model

VerityGraph normalizes every input source before NLP. A PDF, DOCX, TXT file, Wikipedia article, or public URL must ultimately produce the same source contract.

## Why provenance comes first

The pipeline must never create anonymous text that cannot be traced back to origin. Entity extraction, relation extraction, graph analytics, generated insights, feedback and improved response versions will all reference source spans created at ingestion time.

```text
SourceDocument
    |
    +-- SourceSpan 1
    +-- SourceSpan 2
    +-- SourceSpan N
             |
             +-- EntityMention       (future)
             +-- RelationEvidence    (future)
             +-- InsightCitation     (future)
```

## SourceDocument

`SourceDocument` is the canonical metadata envelope for one source.

Core fields:

- `source_id`: opaque VerityGraph identifier.
- `source_type`: document, Wikipedia, or public URL.
- `title`: human-readable source title.
- `filename`: original safe basename for uploaded documents.
- `source_format`: txt, pdf, docx, html, etc.
- `mime_type`: content type accepted by ingestion.
- `content_hash`: SHA-256 of the exact uploaded bytes for reproducibility/deduplication.
- `size_bytes`: source size at ingestion.
- `created_at`: ingestion timestamp.
- `metadata`: source-specific non-secret metadata.

## SourceSpan

A `SourceSpan` is the smallest evidence unit currently passed downstream.

Core fields:

- `span_id`: unique span identifier.
- `source_id`: owning source.
- `text`: normalized extracted text.
- `page_number`: physical PDF page or synthetic page 1 for TXT when available.
- `paragraph_number`: paragraph sequence when available.
- `section`: section/table label when available.
- `char_start`, `char_end`: offsets in VerityGraph's normalized extracted corpus.

The character offsets are intentionally defined against the normalized extracted corpus, not byte offsets inside PDF/DOCX binaries.

## Format-specific provenance in v0.2

### TXT

Text is decoded as UTF-8/UTF-8-SIG first with CP1252 fallback. Blank-line-delimited paragraphs become individual spans. TXT uses synthetic `page_number = 1`.

### PDF

PyMuPDF extracts one normalized evidence span per readable page. Empty pages are skipped. Scanned-image PDFs intentionally fail with a clear message until an OCR adapter is introduced.

### DOCX

Non-empty paragraphs become spans. Table rows are preserved as spans with `section = table_<n>`. DOCX pagination is not inferred because page boundaries are a rendering concern and are not reliably represented by the OOXML document model.

## Invariants

1. Every span belongs to exactly one source.
2. Every span has non-negative offsets and `char_end >= char_start`.
3. Uploaded binary content is hashed before the canonical source is returned.
4. User-supplied paths are reduced to a safe basename; directory traversal strings are never persisted as filenames.
5. Unsupported extensions/MIME combinations are rejected before parsing.
6. Files larger than the configured upload limit are rejected before parser execution.
7. Downstream NLP must consume `SourceSpan` objects rather than untraceable raw strings.

## Persistence roadmap

The v0.2 repository is intentionally in-memory to keep this vertical slice dependency-free and testable. The next persistence adapter will use SQLite by default. The repository interface is isolated so storage can later be replaced by SQLite/PostgreSQL without changing the ingestion or API contracts.
