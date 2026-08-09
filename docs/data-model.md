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
- `filename`: original safe basename for uploaded documents; null for web sources.
- `url`: final public URL when applicable; null for local documents.
- `source_format`: txt, pdf, docx, wikipedia, html, etc.
- `mime_type`: content type accepted by ingestion.
- `content_hash`: SHA-256 for reproducibility/deduplication.
- `size_bytes`: source size at ingestion/normalization.
- `created_at`: ingestion timestamp.
- `metadata`: source-specific non-secret metadata.

Hash semantics depend on the canonical input boundary:

- uploaded document: exact uploaded bytes;
- Wikipedia: normalized selected section text;
- public URL: normalized extracted main text.

This distinction is intentional. For web sources, VerityGraph analyses the selected/extracted evidence view rather than arbitrary navigation/script/advertising markup.

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

The character offsets are intentionally defined against the normalized extracted corpus, not offsets inside PDF/DOCX binaries or remote HTML.

## Format-specific provenance

### TXT

Text is decoded as UTF-8/UTF-8-SIG first with CP1252 fallback. Blank-line-delimited paragraphs become individual spans. TXT uses synthetic `page_number = 1`.

### PDF

PyMuPDF extracts one normalized evidence span per readable page. Empty pages are skipped. Scanned-image PDFs intentionally fail with a clear message until an OCR adapter is introduced.

### DOCX

Non-empty paragraphs become spans. Table rows are preserved as spans with `section = table_<n>`. DOCX pagination is not inferred because page boundaries are a rendering concern and are not reliably represented by the OOXML document model.

### Wikipedia

The official MediaWiki API supplies article search results, revision-aware outlines, and selected sections.

- `SourceDocument.source_type = wikipedia`.
- `url` points to the selected Wikipedia page.
- metadata records `page_id` and `revision_id`.
- each selected article section becomes one or more paragraph-level `SourceSpan` records.
- `SourceSpan.section` stores the human-readable section heading.
- paragraph numbering restarts within each selected section.
- `page_number` is null because web pages do not have stable physical pages.

### Public URL

The SSRF-aware fetcher first obtains a bounded, approved HTML/XHTML/TXT response. Trafilatura then extracts main readable content from those already-fetched bytes.

- `SourceDocument.source_type = public_url`.
- `url` stores the final validated URL after permitted redirects.
- metadata stores requested URL, final URL, hostname, redirect count, HTTP status, fetched byte count, and span count.
- `SourceSpan.section = Main content` in the first extraction version.
- `paragraph_number` records extracted main-content order.
- `page_number` is null because public pages do not have stable physical pages.
- the normalized extracted main text is hashed; raw navigation/script/footer noise is not part of the analysis identity.

## Invariants

1. Every span belongs to exactly one source.
2. Every span has non-negative offsets and `char_end >= char_start`; this is validated by the domain model.
3. Source material is hashed before the canonical source is returned.
4. User-supplied paths are reduced to a safe basename; directory traversal strings are never persisted as filenames.
5. Unsupported extension/MIME combinations are rejected before document parsing.
6. Files larger than the configured upload limit are rejected before parser execution.
7. Public-source provenance retains its final origin URL and source-specific version/transport metadata where available.
8. Public URL retrieval must pass the security boundary before content extraction.
9. Downstream NLP must consume `SourceSpan` objects rather than untraceable raw strings.

## Persistence roadmap

The current repository is intentionally in-memory while the ingestion contracts stabilize. The next persistence adapter will use SQLite by default. The repository interface is isolated so storage can later be replaced by SQLite/PostgreSQL without changing ingestion or API contracts.
