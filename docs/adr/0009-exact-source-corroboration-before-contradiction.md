# ADR 0009: Compare exact source corroboration before inferring contradiction

- Status: Accepted
- Date: 2026-08-09

## Context

VerityGraph can now persist exact evidence, resolve obvious organization aliases, and project an evidence graph. A trust-oriented product also needs to show whether claims are repeated across sources.

The dangerous shortcut is to infer disagreement whenever one source contains a claim and another does not. Silence is not contradiction. A source may omit a fact because of scope, length, timing, editorial focus, or extraction recall.

Historical comparison also requires knowing which sources actually belonged to a specific analysis run rather than looking at the workspace's current membership.

## Decision

VerityGraph will first implement exact cross-source corroboration as a deterministic projection of one immutable analysis run.

A persisted resolved relation is:

- `cross_source` when retained evidence for that relation comes from at least two distinct source IDs;
- `single_source` when retained evidence comes from exactly one source ID.

The product will explicitly state that missing evidence is not contradiction.

Every new `AnalysisRun` will persist its exact ordered source IDs in an `analysis_run_sources` table. This membership is part of run lineage and is not reconstructed from current workspace state.

Pairwise source comparison will use Jaccard similarity over persisted resolved relation IDs.

## Why exact relation IDs

The relation extractor and deterministic resolver already define the canonical claim representation for a run. Reusing that representation ensures comparison, graph analytics, and evidence inspection operate on the same identity and provenance model.

No second semantic matcher is introduced in the comparison layer.

## Alternatives considered

### Treat missing claims as disagreement

Rejected. Absence is not contradictory evidence and would create misleading source-conflict labels.

### Compare raw sentences with embedding similarity

Deferred. Semantic matching may improve recall later, but it adds model thresholds and false-positive risk before an exact baseline is measured.

### Ask an LLM whether sources agree

Deferred. This would be less reproducible, could hallucinate disagreement, and is unnecessary for exact corroboration.

### Use current workspace membership for historical runs

Rejected. Workspace composition can change after an analysis completes, which would rewrite the apparent comparison population for historical results.

### Assign source trust scores now

Deferred. Number of repeated sources is not the same as independence, authority, or truthfulness. Source-quality scoring requires its own transparent model and evaluation.

## Consequences

### Positive

- users can inspect concrete multi-source support;
- single-source claims are surfaced without being stigmatized as false;
- source overlap is measurable and reproducible;
- historical new runs retain exact source membership;
- comparison inherits entity-resolution and evidence lineage;
- no paid API or new inference model is required.

### Trade-offs

- semantically equivalent but differently extracted predicates may not match;
- paraphrases are not merged by the comparison layer;
- repeated misinformation can still appear corroborated;
- old runs cannot recover zero-claim source membership if it was never persisted;
- contradiction detection remains intentionally absent.

## Follow-up

Contradiction support must begin by retaining explicit assertion polarity/negation during extraction. Only when incompatible assertions both have evidence should the UI expose a contradiction candidate. Silence must continue to be represented as missing support, not opposition.
