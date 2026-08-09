# ADR 0006: Use a local spaCy baseline with immutable evidence-linked analysis runs

- Status: Accepted
- Date: 2026-08-09

## Context

VerityGraph now has durable multi-source workspaces containing canonical source spans. The next layer must extract entities and candidate relationships without breaking the product's evidence-first invariant or introducing a mandatory paid model/API dependency.

A common failure mode in information-extraction demos is to emit a triple plus an unexplained `confidence = 0.9`. Unless that number is calibrated against labelled data, it is not a defensible probability that the claim is true.

The analysis layer also needs reproducibility: the same workspace may be analysed multiple times as extraction logic or model versions change, and old results must remain inspectable instead of being silently overwritten.

## Decision

The first production analysis engine is a free local spaCy pipeline using `en_core_web_sm`.

Each analysis creates a new immutable `AnalysisRun` recording:

- workspace ID;
- pipeline version;
- spaCy model name and installed model version;
- relation extractor version;
- start/completion timestamps and runtime;
- source/span/entity/relation counts;
- status and failure details.

### Entity extraction

The baseline retains graph-relevant named-entity labels such as people, organisations, geopolitical entities, locations, facilities, products, events, national/religious/political groups, laws, and works of art.

Every entity mention stores the original:

```text
source_id -> span_id -> mention text -> character offsets
```

Exact entity normalisation is deliberately conservative in this release: Unicode normalisation, case-folding, punctuation cleanup, and entity label are used to consolidate exact aliases. Full alias/entity resolution is a separate later layer so the original NER evidence is never silently rewritten.

### Relationship extraction

The first relation extractor is dependency-rule based and intentionally explainable. It handles three high-precision patterns:

1. active subject -> root predicate -> direct object;
2. active subject -> root + preposition -> prepositional object;
3. passive subject + agent/by phrase, normalised back to semantic active direction.

Example:

```text
GitHub was acquired by Microsoft.
```

is represented semantically as:

```text
Microsoft --acquire--> GitHub
```

Every emitted relation owns one or more `RelationEvidence` records containing the exact supporting sentence plus its source/span identity and sentence offsets.

### Extraction score semantics

The field is named `extraction_score`, not `confidence`.

It records the relative strength of the transparent rule that fired:

- direct subject/object: 0.92;
- passive agent: 0.90;
- subject/preposition/object: 0.84.

These values are **not calibrated factual probabilities**. The frontend must explicitly state `Rule score ≠ factual probability` until a labelled evaluation/calibration process justifies a probabilistic interpretation.

## Performance

spaCy processes workspace spans through `nlp.pipe()` in batches. Entity spans are indexed by sentence once before relationship candidate extraction. This avoids rescanning all entities for every sentence and keeps the baseline close to linear document traversal plus the number of relation candidates emitted.

## Persistence

Analysis state is stored in SQLite tables for:

- analysis runs;
- canonical entities for each run;
- entity mentions;
- relations;
- relation evidence.

Foreign keys connect analysis evidence back to durable canonical sources and spans. Re-running analysis creates a new run ID rather than mutating a previous result.

## Why not an LLM first?

An LLM extractor may be added later as an optional local engine, but starting with a deterministic baseline provides:

- zero mandatory inference/API cost;
- reproducible behaviour;
- explicit error modes;
- explainable extraction paths;
- a benchmark baseline for evaluating whether a later LLM/hybrid engine actually improves precision/recall/F1.

## QA

The NLP release must be tested with the real local spaCy model rather than a mocked parser.

Required layers:

1. active-voice relation extraction test;
2. passive-voice semantic-direction test;
3. cross-source exact entity-consolidation test;
4. API test proving relation evidence points to persisted `source_id` and `span_id`;
5. SQLite recreation test proving analysis runs survive repository recreation;
6. browser E2E creating a workspace, adding evidence, running the real local model, inspecting the extracted relation/evidence, reloading, and restoring the latest analysis from SQLite.

## Consequences

### Positive

- fully local/free baseline;
- explainable candidate relations;
- evidence lineage is present from the first NLP release;
- model/extractor version changes are auditable;
- later graph construction can consume persisted analysis records instead of re-parsing raw text;
- future evaluation can compare deterministic, local-LLM, and hybrid engines fairly.

### Trade-offs

- exact normalisation does not yet solve aliases such as `International Business Machines` vs `IBM`;
- dependency rules trade recall for transparency and precision-oriented behaviour;
- spaCy NER/parser errors flow into downstream extraction;
- extraction scores require future gold-data evaluation before they can be calibrated or described as confidence.
