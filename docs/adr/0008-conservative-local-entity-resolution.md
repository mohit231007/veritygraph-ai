# ADR 0008: Use conservative deterministic entity resolution before graph projection

- Status: Accepted
- Date: 2026-08-09

## Context

The spaCy baseline creates exact normalized entities from named mentions. That is safe but produces duplicate identities when the same organization appears under legal-name variants or an unambiguous acronym. Duplicate nodes fragment relation evidence and distort graph analytics.

A resolver therefore needs to run after extraction but before persistence and graph projection.

## Decision

VerityGraph will begin with a deterministic, organization-only alias resolver.

The initial resolver merges:

1. organization names that differ only by a trailing legal suffix;
2. an uppercase acronym when exactly one multi-token organization in the current analysis corpus expands to that acronym.

Ambiguous acronym matches remain separate.

The resolver remaps relations to canonical entity IDs, consolidates duplicate triplets while retaining distinct evidence, and removes self-loops created solely by alias collapse.

Every immutable `AnalysisRun` records the resolver version. Historical SQLite databases are migrated in place and old runs receive `resolver_version = "none"`.

## Why resolution happens before persistence

Persisting resolved entities means all downstream consumers—API clients, graph analytics, evidence inspection, future insight generation, and GraphRAG—see one consistent identity model for the run.

Original mention strings are still preserved with source/span/offset lineage, so resolution does not erase what the source actually said.

## Alternatives considered

### Fuzzy string matching

Deferred. Edit-distance rules can accidentally merge unrelated short names and require threshold calibration.

### Embedding similarity

Deferred. Embeddings improve semantic recall but introduce model/runtime dependencies and need labelled evaluation before they are allowed to mutate graph identity.

### LLM-based entity judgement

Deferred. It is less deterministic, harder to reproduce offline, and would weaken the zero-cost local baseline unless introduced as an optional evaluated adapter.

### External entity-linking service

Deferred. Useful for global identifiers, but it adds network availability, privacy, rate-limit, and dependency concerns.

### Resolve only inside the graph layer

Rejected. Non-graph consumers would then see a different identity system from the graph, and persisted relations would remain fragmented.

## Consequences

### Positive

- obvious organization aliases become one entity and one graph node;
- relation evidence aggregates under the canonical identity;
- graph metrics become less fragmented;
- merge decisions are explainable and reproducible;
- original mention provenance remains intact;
- no paid API, embedding model, or hosted service is required.

### Trade-offs

- recall is intentionally limited;
- cross-type NER mistakes are not repaired;
- ambiguous acronyms remain unresolved;
- subsidiaries, former names, brands, and semantic aliases are not inferred;
- global real-world entity IDs are not yet assigned.

## Follow-up

Future resolution releases should add labelled pair/cluster evaluation before introducing fuzzy, embedding, registry, or LLM-assisted candidates. Suggested next additions are explicit parenthetical aliases, curated alias overrides, and optional confidence-ranked candidate review rather than silent automatic merging.
