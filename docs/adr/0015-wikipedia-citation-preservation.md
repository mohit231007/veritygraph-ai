# ADR 0015: Preserve Selected-Section Wikipedia Citation Lineage Before Prose Normalization

## Status

Accepted

## Context

VerityGraph already preserves visible URLs, retained public-HTML anchors, DOCX hyperlink relationships, and PDF URI annotations as explicit source-reference provenance. The Wikipedia adapter still lost a stronger signal: MediaWiki inline citation markers such as `[1]` and the external URLs in their corresponding `cite_note` entries were removed before canonical prose spans were created.

Importing the entire page reference list would overstate the selected evidence scope. If a user imports only one section, citations used only by unselected sections must not silently become provenance for that imported source slice.

Likewise, article prose and bibliography text serve different roles and must not be collapsed into one NLP span.

## Decision

For live MediaWiki imports, VerityGraph performs one full-page parse only to construct a citation-note catalog. It then fetches the user-selected sections as before.

For each selected section:

1. canonical prose paragraphs are created with `sup.reference` markers removed from the NLP text;
2. inline `sup.reference a[href="#cite_note-..."]` markers are inspected before removal;
3. only markers that occur in the selected section are resolved against the full-page citation catalog;
4. explicit HTTP(S) targets found in the matching `cite_note` entry become `WikipediaFetchedReference` records;
5. the cleaned citing paragraph remains `context_text` and maps to its canonical `SourceSpan` when uniquely identifiable;
6. the bibliography/footnote entry is retained separately as `reference_text`;
7. the visible marker label and marker identity are retained as `citation_label` and `citation_marker`.

If the user explicitly selects a References section, direct external HTTP(S) links in selected `li[id^="cite_note-"]` entries are also retained with extraction method `mediawiki_reference_list_v1`.

The inline-citation extraction method is `mediawiki_inline_citation_v1`.

## Scope rule

```text
citation exists elsewhere on page
+ marker absent from selected section
=> do not import that citation
```

The full-page citation catalog is lookup metadata only. It does not broaden the user-selected evidence scope.

## Separation of evidence layers

A preserved Wikipedia citation can therefore contain:

```text
context_text       = cleaned article sentence that cited the note
reference_text     = bibliography / cite-note entry text
citation_label     = visible marker such as [1]
citation_marker    = MediaWiki identity such as cite_note-source-1
target_url         = explicit external HTTP(S) target
span_id            = exact citing SourceSpan when deterministic
```

The target URL and bibliography entry are not injected into the canonical article sentence used by NLP.

## Storage migration

`source_references` receives nullable additive columns:

- `reference_text`
- `citation_label`
- `citation_marker`

Historical references remain valid with `NULL` values. VerityGraph does not reconstruct missing citation markers or bibliography text from historical sources.

## Reference identity

Citation marker identity participates in deterministic reference identity and deduplication. If the same target URL is cited through two distinct MediaWiki note markers in one span, both explicit citation bridges can remain inspectable.

## Non-claims

A Wikipedia citation marker and external link do **not** prove:

- that the cited source supports the article sentence;
- that Wikipedia quoted the target accurately;
- endorsement or agreement;
- source independence;
- publisher authority;
- factual truth.

The preserved object means only that the selected Wikipedia content explicitly connected the citing context to that reference entry and URL.

## Interaction with workspace lineage

Workspace reference-lineage advances to `explicit-reference-lineage-v3-wikipedia-citations` and exposes the citing context, bibliography entry, citation marker, and resolved/external target state.

URL target resolution remains unchanged:

```text
0 matching workspace URL identities -> external
1 matching workspace source        -> workspace_unique
2+ matching workspace sources      -> workspace_ambiguous
```

Citation preservation does not alter graph topology, relation extraction, contradiction promotion, source corroboration, source-relationship signals, or extraction scores.

## Consequences

### Benefits

- selected Wikipedia evidence no longer loses its explicit external citation chain;
- references from unselected sections cannot silently expand provenance scope;
- article prose and bibliography text remain auditable as separate evidence layers;
- exact MediaWiki marker identity survives SQLite reload;
- future citation-graph analysis has a deterministic substrate.

### Limitations

- the provider currently focuses on MediaWiki `cite_note` / `sup.reference` conventions;
- templates or custom citation markup outside that convention may be missed;
- multiple external URLs in one cite-note entry are retained as separate references without semantic ranking;
- citation intent, stance, and support are not classified;
- DOI-only or bibliographic entries without explicit HTTP(S) links remain unresolved;
- reference-list text normalization may include MediaWiki display punctuation and does not attempt bibliographic field parsing.

## Rejected alternatives

### Import every external link from the full page

Rejected because it would violate selected-section evidence scope and include unrelated navigation/reference material.

### Keep citation markers inside canonical NLP prose

Rejected because marker tokens such as `[1]` are provenance syntax rather than assertion content.

### Treat a resolved cite-note as supporting evidence automatically

Rejected because the existence of a citation does not establish that the target actually supports the article claim.

### Use an LLM to interpret citation stance now

Rejected until deterministic citation capture is benchmarked and a labelled evaluation set exists.

## Next extensions

1. DOI/arXiv/ISBN and bibliographic identifier extraction when no URL is present;
2. citation support/stance evaluation with labelled data;
3. citation graph analytics over explicit reference edges;
4. publisher/organization identity resolution for referenced sources;
5. canonical URL / redirect equivalence within the existing SSRF boundary.
