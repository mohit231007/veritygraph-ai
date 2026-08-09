# Wikipedia Citation Lineage

VerityGraph preserves selected Wikipedia citation links as provenance metadata without folding bibliography text or hidden URLs into canonical NLP prose.

## Selected-section rule

The MediaWiki adapter builds a full-page `cite_note` lookup catalog, but the catalog does not broaden the imported evidence scope.

```text
citation exists somewhere on the page
+ no matching citation marker in a selected section
=> citation is not imported
```

Only citation markers actually observed in selected content can resolve through the catalog.

If a References section itself is selected, direct external HTTP(S) links in selected `cite_note` entries may also be retained.

## Preserved layers

A retained inline Wikipedia citation can carry:

```text
SourceSpan.text
    cleaned article prose, with [1]-style marker syntax removed

SourceReference.context_text
    cleaned citing sentence / block

SourceReference.citation_label
    visible marker such as [1]

SourceReference.citation_marker
    MediaWiki identity such as cite_note-source-1

SourceReference.reference_text
    bibliography / footnote entry text

SourceReference.target_url
    explicit external HTTP(S) URL from the matching cite-note entry
```

When the cleaned citing context maps uniquely to one selected `SourceSpan`, `span_id` and its paragraph locator are retained as well. If the mapping is ambiguous, VerityGraph preserves the citation record without guessing a span.

## What is not changed

The target URL, citation marker, and bibliography entry are not injected into canonical article prose. They therefore do not create new named entities, relations, polarity, modality, time scope, or graph connectivity merely because a citation exists.

Citation preservation does not alter:

- entity resolution;
- relation extraction;
- graph analytics;
- source corroboration;
- contradiction candidates;
- source-relationship review signals;
- extraction-rule scores.

## What a citation does not prove

A retained citation means that the selected Wikipedia content explicitly connected a citing context to a MediaWiki reference entry and an external target URL.

It does not prove that:

- the external source actually supports the Wikipedia sentence;
- the source was quoted accurately;
- Wikipedia agrees with or endorses the source;
- the target is authoritative;
- the source is independent;
- the cited claim is true.

Those are separate semantic or evaluative questions.

## Workspace resolution

The target URL participates in the existing workspace lineage projection:

```text
no matching workspace URL identity -> external
one matching source                -> workspace_unique
multiple matching sources          -> workspace_ambiguous
```

A later ingest can therefore turn an external Wikipedia citation target into a uniquely or ambiguously resolved workspace source without changing the original citation provenance.

## Current limitations

The deterministic baseline focuses on standard MediaWiki `sup.reference` / `cite_note` markup and explicit HTTP(S) targets. It may miss template-specific citation markup, bibliography entries with identifiers but no URL, or citation relationships that require semantic interpretation.

Next deterministic extensions should prioritize DOI, arXiv, ISBN and other explicit bibliographic identifiers before introducing citation-support or stance classification.
