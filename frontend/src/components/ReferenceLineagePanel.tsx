import { useEffect, useMemo, useState } from "react";

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
  reference_text: string | null;
  citation_label: string | null;
  citation_marker: string | null;
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

type ReferenceTargetGroup = {
  key: string;
  normalizedTargetUrl: string;
  domain: string;
  resolution: ReferenceResolution;
  sourceLabels: string[];
  targetLabels: string[];
  occurrences: ReferenceLineageEdge[];
  searchableText: string;
};

type ResolutionFilter = "all" | ReferenceResolution;

type Props = {
  apiHealthy: boolean;
  workspace: WorkspaceDetail | null;
};

const INITIAL_TARGET_LIMIT = 24;
const RESOLUTION_PRIORITY: Record<ReferenceResolution, number> = {
  external: 0,
  workspace_unique: 1,
  workspace_ambiguous: 2,
};

function resolutionLabel(resolution: ReferenceResolution) {
  if (resolution === "workspace_unique") return "Workspace source";
  if (resolution === "workspace_ambiguous") return "Ambiguous workspace URL";
  return "External / not ingested";
}

function targetLabel(group: ReferenceTargetGroup) {
  if (group.targetLabels.length === 1) return group.targetLabels[0];
  if (group.targetLabels.length > 1) return group.targetLabels.join(" · ");
  return group.normalizedTargetUrl;
}

function locatorLabel(edge: ReferenceLineageEdge) {
  const parts: string[] = [];
  if (edge.page_number !== null) parts.push(`Page ${edge.page_number}`);
  if (edge.paragraph_number !== null) parts.push(`Paragraph ${edge.paragraph_number}`);
  if (edge.citation_label) parts.push(`Citation ${edge.citation_label}`);
  if (edge.citation_marker) parts.push(edge.citation_marker);
  if (edge.span_id) parts.push(edge.span_id);
  return parts.join(" · ");
}

function domainLabel(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "") || "unknown host";
  } catch {
    return "unknown host";
  }
}

function buildTargetGroups(references: ReferenceLineageEdge[]): ReferenceTargetGroup[] {
  const mutable = new Map<
    string,
    {
      normalizedTargetUrl: string;
      domain: string;
      resolution: ReferenceResolution;
      sourceLabels: Set<string>;
      targetLabels: Set<string>;
      occurrences: ReferenceLineageEdge[];
    }
  >();

  for (const edge of references) {
    const key = edge.normalized_target_url;
    const current = mutable.get(key);
    if (!current) {
      mutable.set(key, {
        normalizedTargetUrl: edge.normalized_target_url,
        domain: domainLabel(edge.normalized_target_url),
        resolution: edge.resolution,
        sourceLabels: new Set([edge.source_label]),
        targetLabels: new Set(edge.target_labels),
        occurrences: [edge],
      });
      continue;
    }

    current.sourceLabels.add(edge.source_label);
    edge.target_labels.forEach((label) => current.targetLabels.add(label));
    current.occurrences.push(edge);
    if (RESOLUTION_PRIORITY[edge.resolution] > RESOLUTION_PRIORITY[current.resolution]) {
      current.resolution = edge.resolution;
    }
  }

  return Array.from(mutable.entries())
    .map(([key, group]) => {
      const sourceLabels = Array.from(group.sourceLabels).sort();
      const targetLabels = Array.from(group.targetLabels).sort();
      const occurrenceSearchText = group.occurrences
        .flatMap((edge) => [edge.anchor_text, edge.reference_text])
        .filter((value): value is string => Boolean(value))
        .join(" ");
      return {
        key,
        normalizedTargetUrl: group.normalizedTargetUrl,
        domain: group.domain,
        resolution: group.resolution,
        sourceLabels,
        targetLabels,
        occurrences: group.occurrences,
        searchableText: [
          group.normalizedTargetUrl,
          group.domain,
          ...sourceLabels,
          ...targetLabels,
          occurrenceSearchText,
        ]
          .join(" ")
          .toLowerCase(),
      };
    })
    .sort(
      (left, right) =>
        right.occurrences.length - left.occurrences.length ||
        left.normalizedTargetUrl.localeCompare(right.normalizedTargetUrl),
    );
}

export default function ReferenceLineagePanel({ apiHealthy, workspace }: Props) {
  const [lineage, setLineage] = useState<WorkspaceReferenceLineage | null>(null);
  const [message, setMessage] = useState("Add sources to inspect explicit citation lineage.");
  const [query, setQuery] = useState("");
  const [resolutionFilter, setResolutionFilter] = useState<ResolutionFilter>("all");
  const [visibleLimit, setVisibleLimit] = useState(INITIAL_TARGET_LIMIT);
  const [expandedTargets, setExpandedTargets] = useState<Set<string>>(() => new Set());

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

  const targetGroups = useMemo(
    () => buildTargetGroups(lineage?.references ?? []),
    [lineage?.references],
  );
  const singleTargetKey = targetGroups.length === 1 ? targetGroups[0].key : null;

  useEffect(() => {
    setVisibleLimit(INITIAL_TARGET_LIMIT);
    setQuery("");
    setResolutionFilter("all");
    setExpandedTargets(singleTargetKey ? new Set([singleTargetKey]) : new Set());
  }, [lineage?.workspace_id, singleTargetKey]);

  useEffect(() => {
    setVisibleLimit(INITIAL_TARGET_LIMIT);
  }, [query, resolutionFilter]);

  const filteredTargets = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return targetGroups.filter((group) => {
      const resolutionMatches =
        resolutionFilter === "all" || group.resolution === resolutionFilter;
      const queryMatches = !normalizedQuery || group.searchableText.includes(normalizedQuery);
      return resolutionMatches && queryMatches;
    });
  }, [query, resolutionFilter, targetGroups]);

  const domainStats = useMemo(() => {
    const counts = new Map<string, { targetCount: number; occurrenceCount: number }>();
    for (const group of targetGroups) {
      const current = counts.get(group.domain) ?? { targetCount: 0, occurrenceCount: 0 };
      current.targetCount += 1;
      current.occurrenceCount += group.occurrences.length;
      counts.set(group.domain, current);
    }
    return Array.from(counts.entries())
      .map(([domain, countsForDomain]) => ({ domain, ...countsForDomain }))
      .sort(
        (left, right) =>
          right.occurrenceCount - left.occurrenceCount ||
          right.targetCount - left.targetCount ||
          left.domain.localeCompare(right.domain),
      )
      .slice(0, 8);
  }, [targetGroups]);

  const resolvedTargetCount = targetGroups.filter(
    (group) => group.resolution === "workspace_unique",
  ).length;
  const externalTargetCount = targetGroups.filter(
    (group) => group.resolution === "external",
  ).length;
  const visibleTargets = filteredTargets.slice(0, visibleLimit);

  function toggleTarget(key: string) {
    setExpandedTargets((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

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
            <article data-testid="reference-count"><span>Reference occurrences</span><strong>{lineage.summary.reference_count}</strong></article>
            <article data-testid="unique-reference-target-count"><span>Unique targets</span><strong>{targetGroups.length}</strong></article>
            <article data-testid="resolved-reference-count"><span>Resolved occurrences</span><strong>{lineage.summary.resolved_workspace_reference_count}</strong></article>
            <article><span>Resolved unique targets</span><strong>{resolvedTargetCount}</strong></article>
            <article><span>External unique targets</span><strong>{externalTargetCount}</strong></article>
          </div>

          <aside className="reference-lineage-guardrail" data-testid="reference-lineage-guardrail">
            <strong>Explicit URL ≠ endorsement, quotation, dependence, or truth.</strong>
            <p>{lineage.interpretation_note}</p>
          </aside>

          {targetGroups.length > 0 && (
            <div className="reference-explorer" data-testid="reference-explorer">
              <div className="reference-explorer-heading">
                <div>
                  <strong>Reference explorer</strong>
                  <span>
                    {targetGroups.length} unique target{targetGroups.length === 1 ? "" : "s"} from {lineage.summary.reference_count} occurrence{lineage.summary.reference_count === 1 ? "" : "s"}
                  </span>
                </div>
                <div className="reference-explorer-controls">
                  <input
                    type="search"
                    value={query}
                    data-testid="reference-search-input"
                    placeholder="Search URL, domain, source, or citation text"
                    onChange={(event) => setQuery(event.target.value)}
                  />
                  <select
                    aria-label="Reference resolution filter"
                    value={resolutionFilter}
                    onChange={(event) => setResolutionFilter(event.target.value as ResolutionFilter)}
                  >
                    <option value="all">All targets</option>
                    <option value="workspace_unique">Resolved in workspace</option>
                    <option value="external">External / not ingested</option>
                    <option value="workspace_ambiguous">Ambiguous</option>
                  </select>
                </div>
              </div>

              {domainStats.length > 0 && (
                <div className="reference-domain-summary" aria-label="Top reference domains">
                  {domainStats.map((item) => (
                    <button
                      type="button"
                      key={item.domain}
                      title={`Filter references to ${item.domain}`}
                      onClick={() => setQuery(item.domain)}
                    >
                      <strong>{item.domain}</strong>
                      <span>{item.targetCount} target{item.targetCount === 1 ? "" : "s"} · {item.occurrenceCount} occurrence{item.occurrenceCount === 1 ? "" : "s"}</span>
                    </button>
                  ))}
                </div>
              )}

              <p className="reference-explorer-result-count">
                Showing {Math.min(visibleLimit, filteredTargets.length)} of {filteredTargets.length} matching unique target{filteredTargets.length === 1 ? "" : "s"}.
              </p>
            </div>
          )}

          <div className="reference-lineage-list" data-testid="reference-lineage-list">
            {visibleTargets.map((group) => {
              const expanded = expandedTargets.has(group.key);
              return (
                <section className="reference-target-group" key={group.key} data-testid="reference-lineage-target">
                  <button
                    type="button"
                    className="reference-target-toggle"
                    aria-expanded={expanded}
                    onClick={() => toggleTarget(group.key)}
                  >
                    <span className="reference-target-heading">
                      <strong>{targetLabel(group)}</strong>
                      <small>
                        {group.domain} · {group.occurrences.length} occurrence{group.occurrences.length === 1 ? "" : "s"} · {group.sourceLabels.length} citing source{group.sourceLabels.length === 1 ? "" : "s"}
                      </small>
                    </span>
                    <span className={`reference-resolution ${group.resolution}`}>
                      {resolutionLabel(group.resolution)}
                    </span>
                    <span className="reference-expand-icon" aria-hidden="true">{expanded ? "−" : "+"}</span>
                  </button>
                  <p className="reference-target">{group.normalizedTargetUrl}</p>
                  <p className="reference-citing-sources">Cited by · {group.sourceLabels.join(" · ")}</p>

                  {expanded && (
                    <div className="reference-occurrence-list">
                      {group.occurrences.map((edge, index) => {
                        const locator = locatorLabel(edge);
                        return (
                          <article key={edge.reference_id} data-testid="reference-lineage-edge">
                            <div className="reference-occurrence-heading">
                              <strong>Occurrence {index + 1}</strong>
                              <span>{edge.source_label}</span>
                            </div>
                            {locator && <p data-testid="reference-locator">{locator}</p>}
                            {edge.anchor_text && <p>Anchor · {edge.anchor_text}</p>}
                            {edge.context_text && (
                              <blockquote data-testid="reference-citing-context">“{edge.context_text}”</blockquote>
                            )}
                            {edge.reference_text && (
                              <p data-testid="reference-entry">Reference entry · {edge.reference_text}</p>
                            )}
                            <footer>
                              {edge.extraction_method}
                              {edge.self_reference ? " · self-reference" : ""}
                            </footer>
                          </article>
                        );
                      })}
                    </div>
                  )}
                </section>
              );
            })}

            {targetGroups.length === 0 && (
              <p className="reference-lineage-empty">No explicit HTTP(S) references were retained from the current workspace sources.</p>
            )}
            {targetGroups.length > 0 && filteredTargets.length === 0 && (
              <p className="reference-lineage-empty">No unique reference target matches the current search and resolution filter.</p>
            )}
            {filteredTargets.length > visibleTargets.length && (
              <button
                type="button"
                className="reference-show-more"
                onClick={() => setVisibleLimit((current) => current + INITIAL_TARGET_LIMIT)}
              >
                Show {Math.min(INITIAL_TARGET_LIMIT, filteredTargets.length - visibleTargets.length)} more targets
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
}
