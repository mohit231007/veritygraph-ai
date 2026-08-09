# ADR 0013: Preserve Explicit Reference Lineage Before Inferring Citation Semantics

## Status

Accepted

## Context

VerityGraph can now compare source support and surface deterministic source-relationship review signals, but exact duplicate text or shared origin is still indirect evidence about how sources may relate.

A stronger provenance signal exists when a source itself contains an explicit HTTP(S) target. That reference should be preserved before downstream extraction removes link structure, and it should remain traceable to the exact retained evidence span whenever possible.

However, an explicit link alone does not tell us why the author linked it. It may be a citation, background reading, navigation, criticism, a data source, an embedded asset, or something else. VerityGraph must therefore retain the observable reference without inventing semantic intent.

## Decision

`SourceBundle` now contains first-class `SourceReference` records in addition to the canonical document and evidence spans.

A source reference stores:

```text
reference_id
source_id
span_id?                 # only when exact span mapping is deterministic
target_url
normalized_target_url
anchor_text?
context_text?
extraction_method
```

References are persisted in SQLite and restored with the source bundle.

### Document baseline

PDF, DOCX, and TXT ingestion retains HTTP(S) URLs that are literally visible inside a parsed `SourceSpan`.

The reference points back to that exact span. This baseline does not yet inspect hidden DOCX hyperlink relationships or PDF link annotations when the target URL is not present in extracted text.

### Public HTML baseline

Public HTML ingestion may retain an `<a href>` target only when the anchor's nearest paragraph/list/table-row text maps exactly to a `SourceSpan` that survived the main-content extraction pipeline.

This intentionally rejects unrelated navigation/footer anchors that were not retained as evidence.

Visible HTTP(S) URLs in retained public-page text are also preserved.

### Wikipedia baseline

Wikipedia imports retain HTTP(S) URLs only when they are visible in the selected normalized evidence text. The current provider removes footnote/reference markup before canonical span creation, so this release does not claim to preserve Wikipedia's complete citation graph.

That limitation is explicit rather than reconstructed from lost markup.

## URL identity

Reference target matching is deterministic and conservative:

- HTTP and HTTPS only;
- lowercase scheme and IDNA-normalized hostname;
- default ports removed;
- path and query retained;
- fragment removed;
- no redirect fetching or semantic URL equivalence during lineage projection.

The persisted raw `target_url` remains available beside `normalized_target_url`.

## Workspace resolution

`GET /api/v1/workspaces/{workspace_id}/reference-lineage` projects references against URL identities of sources currently in the workspace.

Possible states are:

```text
external
workspace_unique
workspace_ambiguous
```

A source document contributes URL aliases from its canonical `url` plus persisted `requested_url` / `final_url` metadata when present.

If one workspace source matches the normalized target, the edge is `workspace_unique`.

If multiple workspace sources match the same normalized target, VerityGraph retains every candidate source ID and marks the edge `workspace_ambiguous`. It does not choose one arbitrarily.

If no workspace source matches, the edge is `external`. This means only that the target is not currently resolved to a workspace source; it does not mean the target is missing from the public web or invalid.

## Non-claims

An explicit reference does **not** by itself prove:

- quotation;
- factual support;
- endorsement;
- agreement;
- dependence;
- direction of copying;
- publisher relationship;
- source quality;
- truth.

Likewise, absence of an extracted reference does not prove that a document contains no citation. Some formats and citation styles are not yet captured by this deterministic baseline.

## Interaction with source relationship signals

Explicit reference lineage is a stronger observable provenance signal than exact-text similarity, but Phase 12 does not silently convert it into a derivation verdict.

The Phase 11 `possible_derivation_signal` remains unchanged. Future work may display explicit citation edges beside relationship review signals, but causal interpretation must remain a separate reviewed layer.

## Interaction with graph and contradiction logic

Reference lineage does not currently alter:

- entity/relation extraction;
- graph topology or PageRank;
- assertion polarity/modality/time semantics;
- source corroboration;
- contradiction candidate promotion;
- extraction scores.

It is a provenance projection, not a factual inference engine.

## Consequences

### Benefits

- explicit references survive source ingestion and SQLite reload;
- citation inspection has exact span provenance when observable;
- workspace source-to-source edges can be resolved without external APIs;
- unresolved external targets remain visible instead of disappearing;
- duplicate URL targets are handled as ambiguity rather than guessed identity;
- future citation-graph analytics have a trustworthy deterministic substrate.

### Limitations

- hidden DOCX hyperlinks are not yet extracted;
- PDF link annotations are not yet extracted unless the URL is visible in text;
- Wikipedia reference-list markup is not yet preserved by the provider;
- citation intent and stance are unknown;
- URL normalization is exact, not redirect/canonical-tag equivalence;
- non-URL citation styles such as DOI-only, ISBN, footnote numbers, and bibliographic prose are not yet resolved.

## Rejected alternatives

### Treat every HTML anchor as a citation

Rejected because navigation, footer, social, and UI links would create large amounts of false provenance.

### Treat a URL match as proof of source dependence

Rejected because linking can express many different relationships.

### Resolve duplicate workspace URLs to the newest source

Rejected because ingest order is not evidence of identity preference.

### Use an LLM to classify citation intent immediately

Rejected for the baseline because the observable reference should be preserved first, before introducing an uncalibrated semantic classifier.

## Next extensions

1. DOCX hyperlink relationship extraction;
2. PDF link annotation extraction;
3. Wikipedia footnote/reference preservation;
4. DOI/ISBN/arXiv and bibliographic identifier parsing;
5. canonical-link / redirect lineage with the existing SSRF boundary;
6. explicit citation graph analytics;
7. citation intent/stance only after labelled evaluation.
