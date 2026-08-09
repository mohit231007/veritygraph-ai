import { useEffect, useState } from "react";

import "../bibliographic-identity.css";
import type { WorkspaceDetail } from "../types";

type IdentifierKind = "doi" | "arxiv" | "isbn";
type IdentifierRole = "mention" | "reference" | "source_identity";
type IdentifierResolution =
  | "no_workspace_match"
  | "workspace_unique"
  | "workspace_ambiguous";

type IdentifierObservation = {
  identifier_id: string;
  source_id: string;
  source_label: string;
  kind: IdentifierKind;
  raw_value: string;
  normalized_value: string;
  role: IdentifierRole;
  version: number | null;
  span_id: string | null;
  reference_id: string | null;
  page_number: number | null;
  paragraph_number: number | null;
  resolution: IdentifierResolution;
  matching_source_ids: string[];
  matching_labels: string[];
  identity_target_resolution: IdentifierResolution;
  identity_target_source_ids: string[];
  identity_target_labels: string[];
  context_text: string | null;
  extraction_method: string;
};

type WorkspaceIdentifierLineage = {
  workspace_id: string;
  lineage_version: string;
  summary: {
    source_count: number;
    observation_count: number;
    unique_identifier_count: number;
    matched_observation_count: number;
    ambiguous_observation_count: number;
    reference_linked_observation_count: number;
    source_identity_observation_count: number;
    resolved_identity_target_observation_count: number;
    ambiguous_identity_target_observation_count: number;
  };
  identifiers: IdentifierObservation[];
  interpretation_note: string;
};

type Props = {
  apiHealthy: boolean;
  workspace: WorkspaceDetail | null;
};

function sharedObservationLabel(observation: IdentifierObservation) {
  if (observation.resolution === "workspace_unique") return "Shared by one other source";
  if (observation.resolution === "workspace_ambiguous") return "Shared by multiple sources";
  return "No other source observation";
}

function identityTargetLabel(observation: IdentifierObservation) {
  if (observation.identity_target_resolution === "workspace_unique") {
    return `Resolved source identity · ${observation.identity_target_labels[0]}`;
  }
  if (observation.identity_target_resolution === "workspace_ambiguous") {
    return `Ambiguous source identity · ${observation.identity_target_labels.join(" · ")}`;
  }
  return null;
}

function roleLabel(role: IdentifierRole) {
  if (role === "source_identity") return "Source identity attestation";
  if (role === "reference") return "Reference-linked";
  return "Source mention";
}

function locatorLabel(observation: IdentifierObservation) {
  const parts: string[] = [];
  if (observation.page_number !== null) parts.push(`Page ${observation.page_number}`);
  if (observation.paragraph_number !== null) {
    parts.push(`Paragraph ${observation.paragraph_number}`);
  }
  if (observation.span_id) parts.push(observation.span_id);
  if (observation.reference_id) parts.push(`Reference ${observation.reference_id}`);
  return parts.join(" · ");
}

function identityLabel(observation: IdentifierObservation) {
  const kind = observation.kind === "arxiv" ? "arXiv" : observation.kind.toUpperCase();
  const version = observation.version === null ? "" : ` · observed v${observation.version}`;
  return `${kind} · ${observation.normalized_value}${version}`;
}

export default function BibliographicIdentityPanel({ apiHealthy, workspace }: Props) {
  const [lineage, setLineage] = useState<WorkspaceIdentifierLineage | null>(null);
  const [message, setMessage] = useState(
    "Add sources to inspect DOI, arXiv, and ISBN provenance.",
  );

  useEffect(() => {
    if (!apiHealthy || !workspace) {
      setLineage(null);
      setMessage("Add sources to inspect DOI, arXiv, and ISBN provenance.");
      return;
    }

    const workspaceId = workspace.workspace_id;
    const controller = new AbortController();
    setMessage("Resolving bibliographic observations and attested source identities…");

    async function loadLineage() {
      try {
        const response = await fetch(
          `/api/v1/workspaces/${workspaceId}/identifier-lineage`,
          { signal: controller.signal },
        );
        if (!response.ok) throw new Error("Could not load bibliographic identity lineage.");
        const payload = (await response.json()) as WorkspaceIdentifierLineage;
        setLineage(payload);
        setMessage(
          `Bibliographic identity ready · ${payload.summary.observation_count} observation${payload.summary.observation_count === 1 ? "" : "s"} · ${payload.summary.matched_observation_count} shared across sources · ${payload.summary.resolved_identity_target_observation_count} resolved source identit${payload.summary.resolved_identity_target_observation_count === 1 ? "y" : "ies"} · ${payload.summary.ambiguous_identity_target_observation_count} ambiguous target${payload.summary.ambiguous_identity_target_observation_count === 1 ? "" : "s"}`,
        );
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLineage(null);
        setMessage(
          error instanceof Error
            ? error.message
            : "Could not load bibliographic identity lineage.",
        );
      }
    }

    void loadLineage();
    return () => controller.abort();
  }, [apiHealthy, workspace]);

  return (
    <section
      className="bibliographic-identity-panel"
      aria-labelledby="bibliographic-identity-heading"
      data-testid="bibliographic-identity-panel"
    >
      <div className="bibliographic-identity-heading">
        <div>
          <p className="section-label">BIBLIOGRAPHIC IDENTITY</p>
          <h2 id="bibliographic-identity-heading">DOI, arXiv, and ISBN provenance</h2>
        </div>
        {lineage && <span>{lineage.lineage_version}</span>}
      </div>

      <p
        className="bibliographic-identity-status"
        aria-live="polite"
        data-testid="bibliographic-identity-status"
      >
        {message}
      </p>

      {lineage && (
        <>
          <div className="bibliographic-identity-metrics">
            <article><span>Sources</span><strong>{lineage.summary.source_count}</strong></article>
            <article><span>Observations</span><strong>{lineage.summary.observation_count}</strong></article>
            <article><span>Unique identifiers</span><strong>{lineage.summary.unique_identifier_count}</strong></article>
            <article data-testid="bibliographic-match-count"><span>Shared observations</span><strong>{lineage.summary.matched_observation_count}</strong></article>
            <article><span>Identity attestations</span><strong>{lineage.summary.source_identity_observation_count}</strong></article>
            <article data-testid="resolved-identity-target-count"><span>Resolved identity targets</span><strong>{lineage.summary.resolved_identity_target_observation_count}</strong></article>
          </div>

          <aside
            className="bibliographic-identity-guardrail"
            data-testid="bibliographic-identity-guardrail"
          >
            <strong>Shared identifier ≠ source identity. Source identity ≠ citation, endorsement, authorship, factual support, or truth.</strong>
            <p>{lineage.interpretation_note}</p>
          </aside>

          <div className="bibliographic-identity-list">
            {lineage.identifiers.map((observation) => {
              const locator = locatorLabel(observation);
              const target = identityTargetLabel(observation);
              return (
                <article
                  key={observation.identifier_id}
                  data-testid="bibliographic-identifier-card"
                >
                  <div className="bibliographic-identity-path">
                    <strong>{observation.source_label}</strong>
                    <span>→</span>
                    <strong>{identityLabel(observation)}</strong>
                  </div>
                  <div className="bibliographic-identity-badges">
                    <span className={`identifier-resolution ${observation.resolution}`}>
                      {sharedObservationLabel(observation)}
                    </span>
                    <span>{roleLabel(observation.role)}</span>
                  </div>
                  {observation.matching_labels.length > 0 && (
                    <p>Other source observation{observation.matching_labels.length === 1 ? "" : "s"} · {observation.matching_labels.join(" · ")}</p>
                  )}
                  {target && <p data-testid="identity-target">{target}</p>}
                  {locator && <p className="bibliographic-locator">{locator}</p>}
                  {observation.context_text && <blockquote>“{observation.context_text}”</blockquote>}
                  <footer>{observation.extraction_method}</footer>
                </article>
              );
            })}
            {lineage.identifiers.length === 0 && (
              <p className="bibliographic-identity-empty">
                No explicit DOI, arXiv, or valid ISBN observations were retained from the current workspace sources.
              </p>
            )}
          </div>
        </>
      )}
    </section>
  );
}
