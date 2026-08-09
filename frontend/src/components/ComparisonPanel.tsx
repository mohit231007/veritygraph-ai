import { useEffect, useMemo, useState } from "react";

import "../comparison.css";
import type {
  ClaimSupportLevel,
  ComparisonClaim,
  SourceComparison,
  WorkspaceAnalysis,
  WorkspaceDetail,
} from "../types";

type Filter = "all" | ClaimSupportLevel;

type Props = {
  apiHealthy: boolean;
  workspace: WorkspaceDetail | null;
  analysis: WorkspaceAnalysis | null;
};

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function assertionVerb(
  claim: Pick<ComparisonClaim, "predicate" | "polarity" | "modality">,
) {
  const predicate = claim.polarity === "negated" ? `NOT ${claim.predicate}` : claim.predicate;
  if (claim.modality === "modal") return `MODAL ${predicate}`;
  if (claim.polarity === "unknown" || claim.modality === "unknown") return `? ${predicate}`;
  return predicate;
}

function yearLabel(years: number[]) {
  return years.length > 0 ? `Year ${years.join(", ")}` : "No explicit year";
}

export default function ComparisonPanel({ apiHealthy, workspace, analysis }: Props) {
  const [comparison, setComparison] = useState<SourceComparison | null>(null);
  const [selectedClaim, setSelectedClaim] = useState<ComparisonClaim | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [message, setMessage] = useState("Run an analysis to compare source support.");

  const sourceLabels = useMemo(
    () => new Map(comparison?.sources.map((source) => [source.source_id, source.label]) ?? []),
    [comparison],
  );

  const visibleClaims = useMemo(() => {
    if (!comparison) return [];
    if (filter === "all") return comparison.claims;
    return comparison.claims.filter((claim) => claim.support_level === filter);
  }, [comparison, filter]);

  useEffect(() => {
    const runId = analysis?.run.run_id;
    if (!apiHealthy || !workspace || !runId) {
      setComparison(null);
      setSelectedClaim(null);
      setMessage("Run an analysis to compare source support.");
      return;
    }

    const controller = new AbortController();
    setMessage("Comparing qualified assertions across this run's exact sources…");

    async function loadComparison() {
      try {
        const response = await fetch(`/api/v1/analyses/${runId}/comparison`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Could not compare source support.");
        const payload = (await response.json()) as SourceComparison;
        setComparison(payload);
        setSelectedClaim(payload.claims[0] ?? null);
        setFilter("all");
        setMessage(
          `Comparison ready · ${payload.summary.cross_source_claim_count} cross-source · ${payload.summary.single_source_claim_count} single-source · ${payload.summary.contradiction_candidate_count} contradiction candidate${payload.summary.contradiction_candidate_count === 1 ? "" : "s"}`,
        );
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setComparison(null);
        setSelectedClaim(null);
        setMessage(error instanceof Error ? error.message : "Could not compare source support.");
      }
    }

    void loadComparison();
    return () => controller.abort();
  }, [analysis?.run.run_id, apiHealthy, workspace]);

  return (
    <section className="comparison-panel" aria-labelledby="comparison-heading" data-testid="comparison-panel">
      <div className="comparison-heading">
        <div><p className="section-label">SOURCE COMPARISON</p><h2 id="comparison-heading">Corroboration and scoped evidence conflict</h2></div>
        {comparison && <span className="comparison-version">{comparison.comparison_version}</span>}
      </div>
      <p className="comparison-status" aria-live="polite" data-testid="comparison-status">{message}</p>

      {comparison && (
        <>
          <div className="comparison-metrics" data-testid="comparison-metrics">
            <article><span>Run sources</span><strong>{comparison.summary.source_count}</strong></article>
            <article><span>Claims</span><strong>{comparison.summary.claim_count}</strong></article>
            <article><span>Cross-source</span><strong>{comparison.summary.cross_source_claim_count}</strong></article>
            <article><span>Single-source</span><strong>{comparison.summary.single_source_claim_count}</strong></article>
            <article data-testid="contradiction-count"><span>Conflict candidates</span><strong>{comparison.summary.contradiction_candidate_count}</strong></article>
          </div>

          <aside className="comparison-guardrail" data-testid="comparison-guardrail">
            <strong>Silence, modality, or different time scope ≠ contradiction.</strong>
            <p>{comparison.interpretation_note}</p>
          </aside>

          {comparison.contradictions.length > 0 && (
            <section className="contradiction-section" aria-labelledby="contradiction-heading" data-testid="contradiction-list">
              <div className="comparison-subheading"><div><h3 id="contradiction-heading">Contradiction candidates</h3><span>Asserted only · compatible explicit time scope · evidence on both sides</span></div></div>
              <div className="contradiction-list">
                {comparison.contradictions.map((candidate) => (
                  <article key={candidate.assertion_key} data-testid="contradiction-candidate">
                    <h4>{candidate.subject_label} <span>{candidate.predicate}</span> {candidate.object_label}</h4>
                    <p>{yearLabel(candidate.temporal_years)} · {candidate.source_count} sources · {candidate.evidence_count} evidence records · candidate only, not a truth verdict</p>
                    <div className="contradiction-sides">
                      <div><strong>AFFIRMED</strong>{candidate.affirmed_evidence.map((evidence) => <blockquote key={evidence.evidence_id}><p>“{evidence.text}”</p><footer>{sourceLabels.get(evidence.source_id) ?? evidence.source_id} · {evidence.span_id}</footer></blockquote>)}</div>
                      <div><strong>NEGATED</strong>{candidate.negated_evidence.map((evidence) => <blockquote key={evidence.evidence_id}><p>“{evidence.text}”</p><footer>{sourceLabels.get(evidence.source_id) ?? evidence.source_id} · {evidence.span_id}</footer></blockquote>)}</div>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}

          <div className="source-profile-grid" data-testid="source-profile-list">
            {comparison.sources.map((source) => (
              <article key={source.source_id}>
                <span>{source.source_type?.replaceAll("_", " ") ?? "historical source"}</span><strong>{source.label}</strong>
                <dl><div><dt>Claims</dt><dd>{source.claim_count}</dd></div><div><dt>Corroborated</dt><dd>{source.cross_source_claim_count}</dd></div><div><dt>Only here</dt><dd>{source.single_source_claim_count}</dd></div><div><dt>Conflicts</dt><dd>{source.contradiction_candidate_count}</dd></div></dl>
              </article>
            ))}
          </div>

          <div className="comparison-workbench">
            <section className="claim-browser" aria-labelledby="claim-browser-heading">
              <div className="comparison-subheading">
                <div><h3 id="claim-browser-heading">Resolved qualified assertions</h3><span>Subject · predicate · object · polarity · modality · year scope</span></div>
                <div className="comparison-filters" role="group" aria-label="Claim support filter">
                  {(["all", "cross_source", "single_source"] as const).map((value) => (
                    <button type="button" key={value} aria-pressed={filter === value} data-testid={`comparison-filter-${value}`} onClick={() => setFilter(value)}>
                      {value === "all" ? "All" : value === "cross_source" ? "Cross-source" : "Single-source"}
                    </button>
                  ))}
                </div>
              </div>
              <div className="comparison-claim-list" data-testid="comparison-claim-list">
                {visibleClaims.map((claim) => (
                  <button type="button" key={claim.relation_id} className={selectedClaim?.relation_id === claim.relation_id ? "selected" : ""} onClick={() => setSelectedClaim(claim)}>
                    <div><strong>{claim.subject_label}</strong><span>{assertionVerb(claim)}</span><strong>{claim.object_label}</strong></div>
                    <small>{claim.polarity.toUpperCase()} · {claim.modality.toUpperCase()} · {yearLabel(claim.temporal_years)} · {claim.support_level === "cross_source" ? "Cross-source" : "Single-source"} · {claim.source_count} source{claim.source_count === 1 ? "" : "s"}</small>
                  </button>
                ))}
              </div>
            </section>

            <aside className="comparison-inspector" data-testid="comparison-inspector">
              {!selectedClaim && <p>Select an assertion to inspect its retained source evidence.</p>}
              {selectedClaim && (
                <div data-testid="comparison-claim-detail">
                  <p className="comparison-kicker">{selectedClaim.polarity.toUpperCase()} · {selectedClaim.modality.toUpperCase()} · {yearLabel(selectedClaim.temporal_years)} · {selectedClaim.support_level === "cross_source" ? "CROSS-SOURCE SUPPORT" : "SINGLE-SOURCE EVIDENCE"}</p>
                  <h3>{selectedClaim.subject_label} <span>{assertionVerb(selectedClaim)}</span> {selectedClaim.object_label}</h3>
                  <p>{selectedClaim.source_count} source{selectedClaim.source_count === 1 ? "" : "s"} · {selectedClaim.evidence_count} evidence · rule score {Math.round(selectedClaim.extraction_score * 100)}</p>
                  <div className="comparison-evidence-list">{selectedClaim.evidence.map((evidence) => <blockquote key={evidence.evidence_id}><p>“{evidence.text}”</p><footer>{sourceLabels.get(evidence.source_id) ?? evidence.source_id} · {evidence.span_id}</footer></blockquote>)}</div>
                </div>
              )}
            </aside>
          </div>

          <section className="overlap-section" aria-labelledby="overlap-heading">
            <div className="comparison-subheading"><div><h3 id="overlap-heading">Pairwise claim overlap</h3><span>Exact qualified relation IDs</span></div></div>
            <div className="overlap-list" data-testid="overlap-list">
              {comparison.overlaps.map((overlap) => <article key={`${overlap.left_source_id}-${overlap.right_source_id}`}><div><strong>{sourceLabels.get(overlap.left_source_id) ?? overlap.left_source_id}</strong><span>↔</span><strong>{sourceLabels.get(overlap.right_source_id) ?? overlap.right_source_id}</strong></div><p>{overlap.shared_claim_count} shared / {overlap.union_claim_count} union · {percent(overlap.jaccard_similarity)} overlap</p></article>)}
              {comparison.overlaps.length === 0 && <p className="comparison-empty">Add at least two sources to compute pairwise overlap.</p>}
            </div>
          </section>
        </>
      )}
    </section>
  );
}
