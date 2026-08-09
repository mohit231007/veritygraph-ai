# ADR 0016: Preserve Bibliographic Identifiers as Provenance Before Registry Enrichment

## Status

Accepted

## Context

VerityGraph already preserves explicit URL references, format-level links, and selected Wikipedia citation lineage. Many research and publishing sources also expose stable bibliographic identifiers such as DOI, arXiv IDs, and ISBNs.

Those identifiers can provide a deterministic identity signal even when two sources use different URLs or textual citations. They are useful for provenance, but identifier equality alone does not establish why a source mentions the work or whether the work supports a claim.

The next trust layer should therefore retain and normalize observable identifiers before adding registry lookups, citation-intent inference, or LLM reasoning.

## Decision

`SourceBundle` gains first-class `SourceIdentifier` observations.

Each observation stores:

```text
identifier_id
source_id
kind                    # doi | arxiv | isbn
raw_value
normalized_value
role                    # mention | reference
span_id?
reference_id?
page_number?
paragraph_number?
version?                 # currently used for arXiv
context_text?
extraction_method
```

The observation role is important:

- `mention` means the identifier was explicitly present in retained source text;
- `reference` means the identifier was observed inside already-retained reference text or a supported reference URL.

A body-text identifier is never silently promoted to a citation.

## DOI normalization

The deterministic baseline recognizes explicit DOI strings beginning with `10.` and supported DOI resolver URLs.

Normalization:

1. retain the DOI suffix rather than interpreting its structure;
2. remove only safe surrounding terminal citation punctuation;
3. fold ASCII `A-Z` to `a-z` for identity comparison;
4. retain the original observed value separately.

No DOI registry request occurs during ingestion or workspace projection.

## arXiv normalization

The baseline recognizes explicit `arXiv:` identifiers plus supported `arxiv.org/abs/...` and `arxiv.org/pdf/...` reference URLs.

The normalized identity is the base paper ID. An optional `vN` suffix is retained as `version` rather than becoming part of the identity key.

Therefore two observations of the same base arXiv paper can match while still exposing that different versions were observed. A base-ID match is not a claim that the versions are textually identical.

## ISBN normalization

ISBN extraction is intentionally label-gated: a numeric sequence is considered only when explicitly introduced as `ISBN`, `ISBN-10`, or `ISBN-13`.

Before persistence:

- ISBN-13 values must pass the standard check-digit calculation;
- ISBN-10 values must pass the modulus-11 check, including `X` where valid;
- a valid ISBN-10 is normalized to its equivalent `978` ISBN-13 identity;
- invalid ISBN-shaped strings are discarded.

This allows equivalent ISBN-10 and ISBN-13 forms to match without treating arbitrary long numbers as book identifiers.

## Reference-linked extraction

Identifiers are inspected in three deterministic locations:

```text
SourceSpan.text
SourceReference.reference_text
supported SourceReference.target_url
```

Reference URL extraction is currently limited to DOI resolver and arXiv URL forms. The identifier service does not follow the URL.

## Persistence

SQLite adds a `source_identifiers` table with foreign-key lineage to:

```text
SourceDocument
SourceSpan?
SourceReference?
```

Existing databases create the new table in place. Historical sources are not backfilled or reinterpreted; they have zero identifier rows until they are re-ingested under this pipeline.

## Workspace identity projection

`GET /api/v1/workspaces/{workspace_id}/identifier-lineage` projects exact normalized identifier matches across current workspace sources.

For each observation, the source containing that observation is excluded from its own candidate set.

Resolution states are:

```text
no_workspace_match
workspace_unique
workspace_ambiguous
```

If several other workspace sources carry the same normalized identity, every candidate is retained and the observation remains ambiguous. Import order never selects a preferred source.

## Non-claims

An identifier observation or exact match does **not** by itself prove:

- citation;
- endorsement;
- authorship;
- factual support;
- agreement;
- source dependence;
- copying;
- publication quality;
- currentness;
- truth.

Likewise, absence of an extracted identifier does not prove that a source lacks bibliographic metadata.

## Interaction with existing provenance

Bibliographic identity is a separate projection from URL reference lineage.

A `reference`-role identifier may strengthen the audit trail of an already-retained reference, but Phase 15 does not rewrite URL edges, source-relationship signals, corroboration counts, contradiction promotion, graph topology, or extraction scores.

## Rejected alternatives

### Resolve every identifier through external registries during ingestion

Rejected for this baseline because identity should be preserved locally before adding network availability, rate limits, third-party metadata quality, or SSRF-like trust boundaries.

### Treat every DOI/arXiv/ISBN mention as a citation

Rejected because identifiers can appear in prose, comparisons, bibliographies, examples, or metadata without citation intent.

### Accept ISBN-shaped numbers without checksum validation

Rejected because this would create avoidable false provenance.

### Collapse multiple workspace sources with one identifier

Rejected because duplicate ingestion, mirrors, versions, or different records can legitimately share an identifier identity. Ambiguity must remain visible.

## Consequences

### Benefits

- DOI, arXiv, and ISBN identity survives SQLite reload;
- equivalent ISBN-10/ISBN-13 forms can match deterministically;
- arXiv version observations remain reviewable;
- identifier mentions stay distinct from reference-linked observations;
- exact cross-source identity can be inspected without registry APIs;
- future citation graph and grounded retrieval layers gain a stronger local provenance substrate.

### Limitations

- no DOI/arXiv/ISBN metadata enrichment yet;
- no Crossref, DataCite, arXiv, OpenAlex, or ISBN registry calls;
- no fuzzy title/author matching;
- no citation-intent or citation-stance inference;
- legacy arXiv syntax is supported only when explicitly prefixed or present in a supported arXiv URL;
- identifiers hidden in unsupported binary metadata are not recovered;
- identifier equality does not establish document equivalence.

## Next extensions

1. optional registry enrichment behind explicit network and caching boundaries;
2. identifier-backed citation graph analytics;
3. exact identifier reconciliation for imported source metadata;
4. labelled citation-intent evaluation;
5. hybrid URL + identifier provenance retrieval;
6. grounded GraphRAG over explicitly selected evidence and provenance edges.
