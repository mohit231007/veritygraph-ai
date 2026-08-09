import { useEffect, useMemo, useState } from "react";

import "../analysis.css";
import type { AnalysisEntity, AnalysisRelation, WorkspaceAnalysis, WorkspaceDetail } from "../types";

type AnalysisState = "idle" | "restoring" | "running" | "ready" | "error";

type Props = {
  apiHealthy: boolean;
  workspace: WorkspaceDetail | null;
  onAnalysisChange: (analysis: WorkspaceAnalysis | null) => void;
};

function sourceLabel(workspace: WorkspaceDetail | null, sourceId: string) {
  const source = workspace?.sources.find((item) => item.source_id === sourceId);
  return source ? source.filename ?? source.title : sourceId;
}

function entityAliases(entity: AnalysisEntity) {
  const canonical = entity.canonical_name.toLocaleLowerCase();
  return Array.from(new Set(entity.mentions.map((mention) => mention.text))).filter(
    (alias) => alias.toLocaleLowerCase() !== canonical,
  );
}

function assertionVerb(relation: Pick<AnalysisRelation, "predicate" | "polarity" | "modality">) {
  const predicate = relation.polarity === "negated" ? `NOT ${relation.predicate}` : relation.predicate;
  if (relation.modality === "modal") return `MODAL ${predicate}`;
  if (relation.polarity === "unknown" || relation.modality === "unknown") return `? ${predicate}`;
  return predicate;
}

function yearLabel(years: number[]) {
  return years.length > 0 ? `Year ${years.join(", ")}` : "No explicit year";
}

function analysisMatchesWorkspace(analysis: WorkspaceAnalysis, workspace: WorkspaceDetail) {
  const runSourceIds = [...analysis.run.source_ids].sort();
  const workspaceSourceIds = workspace.sources.map((source) => source.source_id).sort();
  return (
    runSourceIds.length === workspaceSourceIds.length &&
    runSourceIds.every((sourceId, index) => sourceId === workspaceSourceIds[index])
  );
}

export default function AnalysisPanel({ apiHealthy, workspace, onAnalysisChange }: Props) {
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
      onAnalysisChange(null);
      setState("idle");
      setMessage(null);
      return;
    }

    const currentWorkspace = workspace;
    const workspaceId = currentWorkspace.workspace_id;
    const controller = new AbortController();
    setAnalysis(null);
    onAnalysisChange(null);
    setState("restoring");
    setMessage("Checking for the latest persisted analysis and validating its source membership…");

    async function loadLatest() {
      try {
        const response = await fetch(`/api/v1/workspaces/${workspaceId}/analyses/latest`, {
          signal: controller.signal,
        });
        if (response.status === 404) {
          setAnalysis(null);
          onAnalysisChange(null);
          setState("idle");
          setMessage("No analysis run yet. Run the local baseline when this workspace has evidence.");
          return;
        }
        if (!response.ok) throw new Error("Could not load the latest analysis.");
        const restored = (await response.json()) as WorkspaceAnalysis;
        if (!analysisMatchesWorkspace(restored, currentWorkspace)) {
          setAnalysis(null);
          onAnalysisChange(null);
          setState("idle");
          setMessage(
            "Workspace sources changed since the latest completed analysis. Run a new analysis to refresh graph and comparison results.",
          );
          return;
        }
        setAnalysis(restored);
        onAnalysisChange(restored);
        setState("ready");
        setMessage("Latest completed analysis restored from SQLite and matched to the current source set.");
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setAnalysis(null);
        onAnalysisChange(null);
        setState("error");
        setMessage(error instanceof Error ? error.message : "Could not load analysis.");
      }
    }

    void loadLatest();
    return () => controller.abort();
  }, [apiHealthy, onAnalysisChange, workspace]);

  async function runAnalysis() {
    if (!workspace || workspace.source_count === 0) return;
    setState("running");
    setMessage("Running local NER, relations, polarity, modality, year qualifiers and alias resolution…");
    try {
      const response = await fetch(`/api/v1/workspaces/${workspace.workspace_id}/analyses`, {
        method: "POST",
      });
      const payload = (await response.json()) as WorkspaceAnalysis | { detail?: string };
      if (!response.ok) {
        const detail = "detail" in payload && payload.detail ? payload.detail : "Analysis failed.";
        throw new Error(detail);
      }
      const completed = payload as WorkspaceAnalysis;
      setAnalysis(completed);
      onAnalysisChange(completed);
      setState("ready");
      setMessage("Analysis completed locally and persisted as a new immutable run.");
    } catch (error) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "Analysis failed.");
    }
  }

  const analysisBusy = state === "restoring" || state === "running";
  const analysisButtonLabel =
    state === "restoring"
      ? "Restoring analysis…"
      : state === "running"
        ? "Analysing locally…"
        : analysis
          ? "Run new analysis"
          : "Analyse workspace";

  return (
    <section className="analysis-panel" aria-labelledby="analysis-heading" data-testid="analysis-panel">
      <div className="analysis-heading">
        <div><p className="section-label">ANALYSIS ENGINE</p><h2 id="analysis-heading">Evidence-linked NLP baseline</h2></div>
        <button type="button" data-testid="analyse-workspace-button" disabled={!apiHealthy || !workspace || workspace.source_count === 0 || analysisBusy} onClick={() => void runAnalysis()}>
          {analysisButtonLabel}
        </button>
      </div>

      <div className="analysis-context">
        <div><span>Active workspace</span><strong>{workspace?.name ?? "Select or create a workspace"}</strong></div>
        <div><span>Evidence sources</span><strong>{workspace?.source_count ?? 0}</strong></div>
        <p aria-live="polite" data-testid="analysis-status">{message ?? "Waiting for a workspace."}</p>
      </div>

      {analysis && (
        <div className="analysis-results" data-testid="analysis-results">
          <div className="analysis-metrics">
            <article><span>Sources</span><strong>{analysis.run.source_count}</strong></article>
            <article><span>Evidence spans</span><strong>{analysis.run.span_count}</strong></article>
            <article><span>Entities</span><strong>{analysis.run.entity_count}</strong></article>
            <article><span>Relations</span><strong>{analysis.run.relation_count}</strong></article>
            <article><span>Runtime</span><strong>{analysis.run.duration_ms ?? 0} ms</strong></article>
          </div>

          <div className="analysis-provenance">
            <span>Run {analysis.run.run_id}</span>
            <span>{analysis.run.model_name} · {analysis.run.model_version}</span>
            <span>{analysis.run.extractor_version}</span>
            <span>{analysis.run.resolver_version}</span>
          </div>

          <div className="analysis-columns">
            <section aria-labelledby="entities-heading">
              <div className="analysis-subheading"><h3 id="entities-heading">Top entities</h3><span>Exact mentions + conservative deterministic ORG aliases</span></div>
              <div className="entity-list" data-testid="entity-list">
                {analysis.entities.slice(0, 12).map((entity) => {
                  const aliases = entityAliases(entity);
                  return (
                    <article key={entity.entity_id}>
                      <div>
                        <strong>{entity.canonical_name}</strong><span>{entity.entity_type}</span>
                        {aliases.length > 0 && <small className="entity-aliases" data-testid="entity-aliases">Aliases: {aliases.join(", ")}</small>}
                      </div>
                      <span>{entity.mention_count} mention{entity.mention_count === 1 ? "" : "s"}</span>
                    </article>
                  );
                })}
              </div>
            </section>

            <section aria-labelledby="relations-heading">
              <div className="analysis-subheading"><h3 id="relations-heading">Evidence-linked assertions</h3><span>Polarity · modality · explicit year scope · rule score ≠ truth</span></div>
              <div className="relation-list" data-testid="relation-list">
                {analysis.relations.slice(0, 16).map((relation) => (
                  <article className="relation-card" key={relation.relation_id}>
                    <div className="relation-triplet">
                      <strong>{entityNames.get(relation.subject_entity_id) ?? relation.subject_entity_id}</strong>
                      <span>{assertionVerb(relation)}</span>
                      <strong>{entityNames.get(relation.object_entity_id) ?? relation.object_entity_id}</strong>
                    </div>
                    <div className="relation-meta" data-testid="relation-qualifiers">
                      <span>{relation.polarity.toUpperCase()}</span>
                      <span>{relation.modality.toUpperCase()}</span>
                      <span>{yearLabel(relation.temporal_years)}</span>
                      <span>Rule score {Math.round(relation.extraction_score * 100)}</span>
                    </div>
                    {relation.evidence.map((evidence) => (
                      <blockquote key={evidence.evidence_id}><p>“{evidence.text}”</p><footer>{sourceLabel(workspace, evidence.source_id)} · {evidence.span_id}</footer></blockquote>
                    ))}
                  </article>
                ))}
              </div>
            </section>
          </div>

          <aside className="score-callout">
            <strong>Qualifier guardrail</strong>
            <p>New runs retain explicit negation, direct modal/future auxiliaries, and four-digit sentence years. Modal claims and disjoint or one-sided time scopes are not promoted to contradiction candidates. These deterministic signals are not truth probabilities.</p>
          </aside>
        </div>
      )}
    </section>
  );
}
