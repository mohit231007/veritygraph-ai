import { useEffect, useMemo, useState } from "react";

import "../analysis.css";
import type { WorkspaceAnalysis, WorkspaceDetail } from "../types";

type AnalysisState = "idle" | "loading" | "ready" | "error";

type Props = {
  apiHealthy: boolean;
  workspace: WorkspaceDetail | null;
};

function sourceLabel(workspace: WorkspaceDetail | null, sourceId: string) {
  const source = workspace?.sources.find((item) => item.source_id === sourceId);
  return source ? source.filename ?? source.title : sourceId;
}

export default function AnalysisPanel({ apiHealthy, workspace }: Props) {
  const [analysis, setAnalysis] = useState<WorkspaceAnalysis | null>(null);
  const [state, setState] = useState<AnalysisState>("idle");
  const [message, setMessage] = useState<string | null>(null);

  const entityNames = useMemo(
    () => new Map(analysis?.entities.map((entity) => [entity.entity_id, entity.canonical_name]) ?? []),
    [analysis],
  );

  useEffect(() => {
    if (!apiHealthy || !workspace) {
      setAnalysis(null);
      setState("idle");
      setMessage(null);
      return;
    }

    const controller = new AbortController();
    const workspaceId = workspace.workspace_id;
    setState("loading");
    setMessage("Checking for the latest persisted analysis…");

    async function loadLatest() {
      try {
        const response = await fetch(
          `/api/v1/workspaces/${workspaceId}/analyses/latest`,
          { signal: controller.signal },
        );
        if (response.status === 404) {
          setAnalysis(null);
          setState("idle");
          setMessage("No analysis run yet. Run the local baseline when this workspace has evidence.");
          return;
        }
        if (!response.ok) throw new Error("Could not load the latest analysis.");
        setAnalysis((await response.json()) as WorkspaceAnalysis);
        setState("ready");
        setMessage("Latest completed analysis restored from SQLite.");
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState("error");
        setMessage(error instanceof Error ? error.message : "Could not load analysis.");
      }
    }

    void loadLatest();
    return () => controller.abort();
  }, [apiHealthy, workspace]);

  async function runAnalysis() {
    if (!workspace || workspace.source_count === 0) return;

    setState("loading");
    setMessage("Running local NER and evidence-linked dependency extraction…");
    try {
      const response = await fetch(
        `/api/v1/workspaces/${workspace.workspace_id}/analyses`,
        { method: "POST" },
      );
      const payload = (await response.json()) as WorkspaceAnalysis | { detail?: string };
      if (!response.ok) {
        const detail = "detail" in payload && payload.detail ? payload.detail : "Analysis failed.";
        throw new Error(detail);
      }
      setAnalysis(payload as WorkspaceAnalysis);
      setState("ready");
      setMessage("Analysis completed locally and persisted as a new immutable run.");
    } catch (error) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "Analysis failed.");
    }
  }

  return (
    <section className="analysis-panel" aria-labelledby="analysis-heading" data-testid="analysis-panel">
      <div className="analysis-heading">
        <div>
          <p className="section-label">ANALYSIS ENGINE</p>
          <h2 id="analysis-heading">Evidence-linked NLP baseline</h2>
        </div>
        <button
          type="button"
          data-testid="analyse-workspace-button"
          disabled={!apiHealthy || !workspace || workspace.source_count === 0 || state === "loading"}
          onClick={() => void runAnalysis()}
        >
          {state === "loading" ? "Analysing locally…" : analysis ? "Run new analysis" : "Analyse workspace"}
        </button>
      </div>

      <div className="analysis-context">
        <div>
          <span>Active workspace</span>
          <strong>{workspace?.name ?? "Select or create a workspace"}</strong>
        </div>
        <div>
          <span>Evidence sources</span>
          <strong>{workspace?.source_count ?? 0}</strong>
        </div>
        <p aria-live="polite" data-testid="analysis-status">
          {message ?? "Waiting for a workspace."}
        </p>
      </div>

      {analysis && (
        <div className="analysis-results" data-testid="analysis-results">
          <div className="analysis-metrics">
            <article>
              <span>Sources</span>
              <strong>{analysis.run.source_count}</strong>
            </article>
            <article>
              <span>Evidence spans</span>
              <strong>{analysis.run.span_count}</strong>
            </article>
            <article>
              <span>Entities</span>
              <strong>{analysis.run.entity_count}</strong>
            </article>
            <article>
              <span>Relations</span>
              <strong>{analysis.run.relation_count}</strong>
            </article>
            <article>
              <span>Runtime</span>
              <strong>{analysis.run.duration_ms ?? 0} ms</strong>
            </article>
          </div>

          <div className="analysis-provenance">
            <span>Run {analysis.run.run_id}</span>
            <span>
              {analysis.run.model_name} · {analysis.run.model_version}
            </span>
            <span>{analysis.run.extractor_version}</span>
          </div>

          <div className="analysis-columns">
            <section aria-labelledby="entities-heading">
              <div className="analysis-subheading">
                <h3 id="entities-heading">Top entities</h3>
                <span>Exact normalized mentions · alias resolution comes next</span>
              </div>
              <div className="entity-list" data-testid="entity-list">
                {analysis.entities.slice(0, 12).map((entity) => (
                  <article key={entity.entity_id}>
                    <div>
                      <strong>{entity.canonical_name}</strong>
                      <span>{entity.entity_type}</span>
                    </div>
                    <span>
                      {entity.mention_count} mention{entity.mention_count === 1 ? "" : "s"}
                    </span>
                  </article>
                ))}
                {analysis.entities.length === 0 && (
                  <p className="analysis-empty">No selected entity types were detected in this corpus.</p>
                )}
              </div>
            </section>

            <section aria-labelledby="relations-heading">
              <div className="analysis-subheading">
                <h3 id="relations-heading">Evidence-linked relations</h3>
                <span>Rule score ≠ factual probability</span>
              </div>
              <div className="relation-list" data-testid="relation-list">
                {analysis.relations.slice(0, 16).map((relation) => (
                  <article className="relation-card" key={relation.relation_id}>
                    <div className="relation-triplet">
                      <strong>
                        {entityNames.get(relation.subject_entity_id) ?? relation.subject_entity_id}
                      </strong>
                      <span>{relation.predicate}</span>
                      <strong>
                        {entityNames.get(relation.object_entity_id) ?? relation.object_entity_id}
                      </strong>
                    </div>
                    <div className="relation-meta">
                      <span>Rule score {Math.round(relation.extraction_score * 100)}</span>
                      <span>{relation.extraction_method.replaceAll("_", " ")}</span>
                    </div>
                    {relation.evidence.map((evidence) => (
                      <blockquote key={evidence.evidence_id}>
                        <p>“{evidence.text}”</p>
                        <footer>
                          {sourceLabel(workspace, evidence.source_id)} · {evidence.span_id}
                        </footer>
                      </blockquote>
                    ))}
                  </article>
                ))}
                {analysis.relations.length === 0 && (
                  <p className="analysis-empty">
                    No baseline subject/object relations were found. Evidence is preserved for future extractors.
                  </p>
                )}
              </div>
            </section>
          </div>

          <aside className="score-callout">
            <strong>Why “rule score” instead of confidence?</strong>
            <p>
              This number records which transparent extraction rule fired and its relative strength. It is not
              calibrated against a labelled dataset yet, so VerityGraph does not present it as a probability that
              the claim is true.
            </p>
          </aside>
        </div>
      )}
    </section>
  );
}
