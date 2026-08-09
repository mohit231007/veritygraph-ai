# Deterministic Entity Resolution

## Why it exists

Named-entity recognition produces mentions, not a perfect global identity system. Without a resolution step, obvious aliases such as `Microsoft`, `Microsoft Corporation`, and a uniquely identifiable acronym can become separate graph nodes. That fragments relation support and distorts centrality, communities, paths, and future retrieval.

VerityGraph's first resolver is intentionally conservative and local. It resolves only cases that can be explained without embeddings, web lookup, or an LLM.

## Current rules

`deterministic-org-aliases-v1` applies to `ORG` entities only.

### 1. Trailing legal suffix normalization

Organization names are merged when their normalized names differ only by a trailing legal suffix such as:

- Inc / Incorporated
- Corp / Corporation
- Ltd / Limited
- LLC
- PLC
- GmbH
- AG
- SA
- Co / Company

Examples:

```text
Microsoft
Microsoft Corporation
        -> Microsoft
```

Suffix stripping is only used for organization identity. It is not applied to people, locations, products, laws, or other entity types.

### 2. Unique acronym expansion

An uppercase acronym is merged with a multi-token organization only when exactly one candidate organization expands to that initialism within the analysis corpus.

```text
International Business Machines
IBM
        -> International Business Machines
```

If two full organization names both expand to `IBM`, the acronym remains unresolved. Ambiguity is preserved instead of guessed.

Common function words such as `of`, `the`, `and`, and `for` are ignored when computing the initialism.

## Canonical-name selection

Within a resolved group, canonical selection prefers:

1. a non-acronym name;
2. a name without a trailing corporate suffix;
3. the alias with more retained mentions;
4. then a shorter stable display name.

Original mention strings are never discarded. They remain attached to the canonical entity with their source/span/character provenance.

## Relation remapping

After entity resolution:

1. relation subject/object IDs are remapped to canonical entity IDs;
2. a relation that becomes a self-loop only because two aliases collapsed is removed;
3. identical `(subject, predicate, object)` relations are consolidated;
4. all distinct evidence records are retained and repointed to the surviving relation ID;
5. the strongest extraction-rule score/method is retained for the consolidated relation.

This allows multiple aliases to contribute evidence to one graph edge without losing the source sentences that created that support.

## Run lineage

Every `AnalysisRun` stores `resolver_version` alongside:

- spaCy pipeline version;
- model name/version;
- relation extractor version.

Existing SQLite databases are migrated in place. Historical runs created before resolver lineage existed receive `resolver_version = "none"` rather than being rewritten as though they had been resolved.

## What the resolver deliberately does not do

The first release does **not** use:

- fuzzy edit distance;
- semantic embeddings;
- vector similarity;
- external company registries;
- Wikipedia/entity-linking APIs;
- LLM judgement;
- cross-type resolution;
- pronoun/coreference resolution.

Those techniques can improve recall, but they introduce ambiguity and require their own evaluation. VerityGraph starts with high-explainability merges and leaves uncertain aliases separate.

## UI behavior

The analysis panel displays the canonical entity and any retained alternate mention strings as aliases. The graph uses the canonical entity, so PageRank, centrality, community assignment, and connection paths operate on the resolved identity rather than obvious duplicate nodes.

## Evaluation path

Entity resolution should eventually receive its own labelled benchmark with pairwise precision/recall/F1 and cluster-level metrics. The current rule set is covered by deterministic unit tests, a real-model API integration test, SQLite migration coverage, and a full browser journey.
