# ADR 0014: Preserve Format-Level Link Targets Without Rewriting NLP Evidence

## Status

Accepted

## Context

ADR 0013 established first-class explicit URL reference lineage, but the initial baseline could only retain links whose URL was visible in extracted text or retained HTML anchor markup.

DOCX and PDF can carry explicit external link targets separately from visible text:

- DOCX stores external hyperlinks as package relationships referenced by `w:hyperlink` elements;
- PDF stores clickable URI actions as link annotations.

Discarding those targets loses observable provenance. Injecting the hidden URL into canonical text would be equally problematic because it would alter the NLP evidence corpus and could create words or entities that the user never saw in document text.

## Decision

VerityGraph preserves supported format-level link metadata as `SourceReference` records while leaving canonical `SourceSpan` text semantically faithful to visible document text.

`SourceReference` now additionally carries optional:

```text
page_number
paragraph_number
```

These fields are format locators. They do not imply that the target URL itself appeared in extracted text.

## DOCX hyperlinks

For top-level document paragraphs, VerityGraph reads external hyperlink relationships referenced by `w:hyperlink/@r:id`.

For every supported HTTP(S) target it retains:

- the relationship target URL;
- normalized target URL;
- hyperlink display text when available;
- surrounding visible paragraph text;
- matching canonical `SourceSpan` when deterministic;
- canonical paragraph number when a span match exists;
- extraction method `docx_hyperlink_relationship_v1`.

Canonical DOCX paragraph text is built from all visible `w:t` nodes so hyperlink display text remains part of the visible evidence sentence even when `python-docx` object-model behavior differs across versions.

The URL target itself is **not** inserted into the span unless it was already visibly present in the document.

### Current DOCX limitation

This release captures hyperlinks in top-level document paragraphs. Hyperlinks nested inside table cells, headers, footers, text boxes, comments, footnotes, endnotes, or other package parts remain future work.

Internal Word bookmarks/anchors without an external HTTP(S) relationship are not source references.

## PDF URI annotations

For PDF pages, VerityGraph reads PyMuPDF link annotations and retains only URI actions whose target normalizes to HTTP(S).

For each retained link it records:

- target URL and normalized URL;
- page number;
- matching page `SourceSpan` when that page has readable extracted text;
- nearby visible anchor text from the annotation rectangle when PyMuPDF can recover it;
- page evidence text as context when available;
- extraction method `pdf_link_annotation_v1`.

A PDF page link can therefore retain page provenance even when the URL string is absent from extracted page text.

Non-URI link actions such as internal page jumps are not source references.

## Deduplication

When the same target is both visibly printed and represented by richer format metadata in the same source location, VerityGraph keeps one reference and prefers the richer format-level record.

Current priority is:

```text
DOCX hyperlink / PDF annotation / retained HTML anchor
    > visible URL regex
```

This preference changes provenance metadata only; it does not alter canonical text.

## Storage migration

Existing `source_references` tables receive nullable `page_number` and `paragraph_number` columns through additive SQLite migration.

Historical reference rows retain `NULL` locators. No page or paragraph is reconstructed from incomplete historical information.

## Non-claims

A clickable link still does **not** prove:

- citation intent;
- factual support;
- quotation;
- endorsement;
- dependence;
- copying direction;
- truth.

A format locator identifies where a link object was observed, not what rhetorical role the link plays.

## Consequences

### Benefits

- DOCX links whose URLs are hidden behind display text survive ingestion;
- PDF URI annotations survive even when URLs are absent from page text;
- canonical NLP text is not contaminated with hidden relationship targets;
- reviewers get page/paragraph provenance where the format supports it;
- existing workspace URL resolution works unchanged over richer reference input.

### Limitations

- DOCX coverage is currently limited to top-level paragraphs;
- PDF JavaScript, launch actions, attachments, and non-HTTP(S) schemes are excluded;
- PDF link rectangles may not yield reliable anchor text in every file;
- complete bibliographic citation extraction is still out of scope;
- Wikipedia footnote/reference markup still requires a provider-level preservation change.

## Rejected alternatives

### Inject hidden URLs into `SourceSpan.text`

Rejected because hidden package metadata should not silently become NLP evidence.

### Treat all PDF links as source citations

Rejected because internal navigation and non-URI actions are not external source references.

### Parse every DOCX package part immediately

Rejected for this slice because the top-level paragraph relationship path is deterministic and testable; broader package traversal should be added incrementally with explicit provenance semantics.

## Next extensions

1. DOCX table/header/footer/footnote/endnote hyperlink relationships;
2. PDF annotation subtype and surrounding-block provenance;
3. Wikipedia citation/reference preservation before text normalization;
4. DOI, ISBN, arXiv and bibliographic identifier resolution;
5. citation-intent or stance classification only after labelled evaluation.
