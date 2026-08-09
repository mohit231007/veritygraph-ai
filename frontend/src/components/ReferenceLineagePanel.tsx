import { useEffect, useState } from "react";

import "../reference-lineage.css";
import type { WorkspaceDetail } from "../types";

type ReferenceResolution = "external" | "workspace_unique" | "workspace_ambiguous";

type ReferenceLineageEdge = {
  reference_id: string;
  source_id: string;
  source_label: string;
  span_id: string | null;
  page_number: number | null;
  paragraph_number: number | null;
  target_url: string;
  normalized_target_url: string;
  resolution: ReferenceResolution;
  target_source_ids: string[];
  target_labels: string[];
  anchor_text: string | null;
  context_text: string | null;
  extraction_method: string;
  self_reference: boolean;
};

type WorkspaceReferenceLineage = {
  workspace_id: string;
  lineage_version: string;
  summary: {
    source_count: number;
    reference_count: number;
    resolved_workspace_reference_count: number;
    ambiguous_workspace_reference_count: number;
    external_reference_count: number;
    self_reference_count: number;
  };
  references: ReferenceLineageEdge[];
  interpretation_note: string;
};

type Props = {
  apiHealthy: boolean;
  workspace: WorkspaceDetail | null;
};

function resolutionLabel(edge: ReferenceLineageEdge) {
  if (edge.resolution === "workspace_unique") return "Workspace source";
  if (edge.resolution === "workspace_ambiguous") return "Ambiguous workspace URL";
  return "External / not ingested";
}

function targetLabel(edge: ReferenceLineageEdge) {
  if (edge.target_labels.length === 1) return edge.target_labels[0];
  if (edge.target_labels.length > 1) return edge.target_labels.join(" · ");
  return edge.normalized_target_url;
}

function locatorLabel(edge: ReferenceLineageEdge) {
  const parts: string[] = [];
  if (edge.page_number !== null) parts.push(`Page ${edge.page_number}`);
  if (edge.paragraph_number !== null) parts.push(`Paragraph ${edge.paragraph_number}`);
  if (edge.span_id) parts.push(edge.span_id);
  return parts.join(" · ");
}

export default function ReferenceLineagePanel({ apiHealthy, workspace }: Props) {
  const [lineage, setLineage] = useState<WorkspaceReferenceLineage | null>(null);
  const [message, setMessage] = useState("Add sources to inspect explicit citation lineage.");

  useEffect(() => {
    if (!apiHealthy || !workspace) {
      setLineage(null);
      setMessage("Add sources to inspect explicit citation lineage.");
      return;
    }

    const workspaceId = workspace.workspace_id;
    const controller = new AbortController();
    setMessage("Resolving explicit references against workspace source URLs…");

    async function loadLineage() {
      try {
        const response = await fetch(
          `/api/v1/workspaces/${workspaceId}/reference-lineage`,
          { signal: controller.signal },
        );
        if (!response.ok) throw new Error("Could not load reference lineage.");
        const payload = (await response.json()) as WorkspaceReferenceLineage;
        setLineage(payload);
        setMessage(
          `Reference lineage ready · ${payload.summary.reference_count} explicit reference${payload.summary.reference_count === 1 ? "" : "s"} · ${payload.summary.resolved_workspace_reference_count} uniquely resolved · ${payload.summary.ambiguous_workspace_reference_count} ambiguous · ${payload.summary.external_reference_count} external`,
        );
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLineage(null);
        setMessage(error instanceof Error ? error.message : "Could not load reference lineage.");
      }
    }

    void loadLineage();
    return () => controller.abort();
  }, [apiHealthy, workspace]);

  return (
    <section className="reference-lineage-panel" aria-labelledby="reference-lineage-heading" data-testid="reference-lineage-panel">
      <div className="reference-lineage-heading">
        <div>
          <p className="section-label">REFERENCE LINEAGE</p>
          <h2 id="reference-lineage-heading">Explicit source-to-source citations</h2>
        </div>
        {lineage && <span>{lineage.lineage_version}</span>}
      </div>

      <p className="reference-lineage-status" aria-live="polite" data-testid="reference-lineage-status">{message}</p>

      {lineage && (
        <>
          <div className="reference-lineage-metrics" data-testid="reference-lineage-metrics">
            <article><span>Sources</span><strong>{lineage.summary.source_count}</strong></article>
            <article data-testid="reference-count"><span>Explicit references</span><strong>{lineage.summary.reference_count}</strong></article>
            <article data-testid="resolved-reference-count"><span>Unique workspace targets</span><strong>{lineage.summary.resolved_workspace_reference_count}</strong></article>
            <article><span>Ambiguous URL targets</span><strong>{lineage.summary.ambiguous_workspace_reference_count}</strong></article>
            <article><span>External / not ingested</span><strong>{lineage.summary.external_reference_count}</strong></article>
          </div>

          <aside className="reference-lineage-guardrail" data-testid="reference-lineage-guardrail">
            <strong>Explicit URL ≠ endorsement, quotation, dependence, or truth.</strong>
            <p>{lineage.interpretation_note}</p>
          </aside>

          <div className="reference-lineage-list" data-testid="reference-lineage-list">
            {lineage.references.map((edge) => {
              const locator = locatorLabel(edge);
              return (
                <article key={edge.reference_id} data-testid="reference-lineage-edge">
                  <div className="reference-lineage-path">
                    <strong>{edge.source_label}</strong>
                    <span>→</span>
                    <strong>{targetLabel(edge)}</strong>
                  </div>
                  <p className={`reference-resolution ${edge.resolution}`}>{resolutionLabel(edge)}</p>
                  <p className="reference-target">{edge.normalized_target_url}</p>
                  {locator && <p data-testid="reference-locator">{locator}</p>}
                  {edge.anchor_text && <p>Anchor · {edge.anchor_text}</p>}
                  {edge.context_text && <blockquote>“{edge.context_text}”</blockquote>}
                  <footer>
                    {edge.extraction_method}
                    {edge.self_reference ? " · self-reference" : ""}
                  </footer>
                </article>
              );
            })}
            {lineage.references.length === 0 && (
              <p className="reference-lineage-empty">No explicit HTTP(S) references were retained from the current workspace sources.</p>
            )}
          </div>
        </>
      )}
    </section>
  );
}
