# ADR 0017: Separate Shared Bibliographic Observations from Source Identity Attestation

## Status

Accepted

## Context

VerityGraph preserves DOI, arXiv, and ISBN observations from source text and retained references. Phase 15 initially projected an exact normalized identifier observed in two sources as an "identity match".

That wording was too strong.

If two uploaded documents both contain:

```text
DOI:10.1000/example
```

we know only that both documents explicitly mention the same DOI. Neither document has thereby proven that it *is* the work identified by that DOI.

Future citation-graph work needs a stricter target identity boundary. Otherwise a reference-linked DOI could be resolved to any document that merely discusses the same DOI, creating a false source-to-source citation edge.

## Decision

`IdentifierObservationRole` gains a third role:

```text
mention
reference
source_identity
```

The roles mean:

- `mention`: the identifier is explicitly present in retained source evidence text;
- `reference`: the identifier is explicitly present in retained reference text or a supported reference URL;
- `source_identity`: the source acquisition URL itself explicitly identifies the DOI or arXiv work.

The role is persisted in the existing `source_identifiers.role` text column, so no destructive schema migration is required.

## Source identity attestation baseline

Phase 16 attests source identity only from supported acquisition URLs:

```text
https://doi.org/<doi>
https://dx.doi.org/<doi>
https://www.doi.org/<doi>
https://arxiv.org/abs/<id>
https://arxiv.org/pdf/<id>[.pdf]
```

The requested URL and final URL of public-web ingestion are both inspected.

This matters for DOI resolution: a user may request a DOI resolver URL and be redirected to a publisher page. The requested DOI URL remains the explicit identity attestation even when the final fetched URL is a different publisher host.

## Explicit non-attestations

The following do **not** create `source_identity`:

- a DOI/arXiv/ISBN appearing only in PDF, DOCX, TXT, HTML, or Wikipedia body text;
- an identifier appearing only in a bibliography or retained reference;
- a DOI-shaped substring in an arbitrary publisher URL;
- an ISBN in a URL;
- title or author similarity;
- canonical-link inference;
- redirects to or from unsupported hosts without an explicit supported acquisition identity URL;
- registry metadata that was not part of the ingestion request.

An ordinary body mention therefore remains a `mention` even if several sources contain the exact same normalized identifier.

## Workspace projection

`/api/v1/workspaces/{workspace_id}/identifier-lineage` advances to:

```text
bibliographic-identity-lineage-v2-source-attestation
```

Each identifier observation now answers two separate questions.

### 1. Shared observation

Existing fields remain available:

```text
resolution
matching_source_ids
matching_labels
```

They mean only: which *other* workspace sources contain the same normalized identifier observation?

Possible states remain:

```text
no_workspace_match
workspace_unique
workspace_ambiguous
```

These fields are not source-identity resolution.

### 2. Attested source target

New fields are:

```text
identity_target_resolution
identity_target_source_ids
identity_target_labels
```

Only sources containing a `source_identity` observation for the same normalized identifier are eligible targets.

The current source is excluded from its own target candidates. If exactly one other source is attested, the target is `workspace_unique`. If several are attested, all candidates are retained and the target is `workspace_ambiguous`.

Import order never selects a preferred target.

## Summary metrics

The lineage summary adds:

```text
source_identity_observation_count
resolved_identity_target_observation_count
ambiguous_identity_target_observation_count
```

Existing shared-observation counts remain for compatibility, but UI wording is corrected from "exact workspace identity" to "shared observation".

## User-interface guardrail

The browser explicitly states:

```text
Shared identifier ≠ source identity.
Source identity ≠ citation, endorsement, authorship, factual support, or truth.
```

A `source_identity` badge is shown separately from ordinary source mentions and reference-linked identifiers.

## Non-claims

A source-identity attestation does **not** by itself prove:

- citation;
- endorsement;
- authorship;
- factual support;
- agreement;
- dependence;
- copying;
- publication quality;
- truth.

It means only that the source was acquired through an explicitly supported identifier URL that identifies the work.

Likewise, absence of a source-identity attestation does not prove that the source lacks a DOI, arXiv ID, or other canonical identity. The current baseline is intentionally narrower than all possible publisher metadata.

## Why this boundary matters for the next phase

A future explicit citation graph may safely consider:

```text
reference-linked identifier
        -> uniquely attested source_identity target
```

It must not create:

```text
reference-linked identifier
        -> arbitrary source that merely mentions the same identifier
```

That distinction prevents bibliographic co-mention from being mistaken for a source-to-source citation edge.

## Rejected alternatives

### Treat any exact identifier observation as source identity

Rejected because documents frequently discuss, compare, or cite identifiers belonging to other works.

### Infer identity from arbitrary publisher URL paths

Rejected because publisher URL structures are not a universal identifier contract and DOI-shaped path text is insufficient evidence.

### Use title/author similarity as identity attestation

Rejected for this deterministic layer because fuzzy metadata reconciliation needs a separate evaluated confidence model.

### Query DOI/arXiv registries immediately

Rejected for this phase. External enrichment can later strengthen identity, but the local observable boundary must remain explicit and independently reviewable.

## Consequences

### Benefits

- shared identifier observations no longer overclaim source identity;
- DOI resolver redirects retain useful identity provenance;
- future citation edges can target only explicitly attested works;
- ordinary mentions, references, and source identity remain independently auditable;
- existing persisted identifier rows remain compatible because the role column is textual;
- no registry or network dependency is introduced into workspace projection.

### Limitations

- ISBN source identity is not attested in this baseline;
- publisher metadata and `<meta>` citation tags are not used yet;
- DOI/arXiv identity aliases outside the supported host/path forms are not inferred;
- duplicate ingestions of the same attested work remain ambiguous rather than being collapsed;
- source identity is still provenance, not a truth or authority score.

## Next extension

Build an explicit citation graph that combines:

1. uniquely resolved URL reference edges; and
2. reference-linked DOI/arXiv/ISBN observations resolved only to uniquely attested source identities.

Ambiguous and unresolved references remain reviewable but do not become deterministic source-to-source citation edges.
