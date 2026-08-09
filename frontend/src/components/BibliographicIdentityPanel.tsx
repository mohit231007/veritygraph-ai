import { useEffect, useMemo, useState } from "react";

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

type IdentifierGroup = {
  key: string;
  kind: IdentifierKind;
  normalizedValue: string;
  versions: number[];
  sourceLabels: string[];
  roles: IdentifierRole[];
  observations: IdentifierObservation[];
  searchableText: string;
};

type KindFilter = "all" | IdentifierKind;
type RoleFilter = "all" | IdentifierRole;

type Props = {
  apiHealthy: boolean;
  workspace: WorkspaceDetail | null;
};

const INITIAL_IDENTIFIER_LIMIT = 20;

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

function kindLabel(kind: IdentifierKind) {
  return kind === "arxiv" ? "arXiv" : kind.toUpperCase();
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
  const version = observation.version === null ? "" : ` · observed v${observation.version}`;
  return `${kindLabel(observation.kind)} · ${observation.normalized_value}${version}`;
}

function buildIdentifierGroups(observations: IdentifierObservation[]): IdentifierGroup[] {
  const mutable = new Map<
    string,
    {
      kind: IdentifierKind;
      normalizedValue: string;
      versions: Set<number>;
      sourceLabels: Set<string>;
      roles: Set<IdentifierRole>;
      observations: IdentifierObservation[];
    }
  >();

  for (const observation of observations) {
    const key = `${observation.kind}:${observation.normalized_value}`;
    const current = mutable.get(key);
    if (!current) {
      mutable.set(key, {
        kind: observation.kind,
        normalizedValue: observation.normalized_value,
        versions: new Set(observation.version === null ? [] : [observation.version]),
        sourceLabels: new Set([observation.source_label]),
        roles: new Set([observation.role]),
        observations: [observation],
      });
      continue;
    }
    if (observation.version !== null) current.versions.add(observation.version);
    current.sourceLabels.add(observation.source_label);
    current.roles.add(observation.role);
    current.observations.push(observation);
  }

  return Array.from(mutable.entries())
    .map(([key, group]) => {
      const versions = Array.from(group.versions).sort((left, right) => left - right);
      const sourceLabels = Array.from(group.sourceLabels).sort();
      const roles = Array.from(group.roles).sort();
      const occurrenceText = group.observations
        .flatMap((observation) => [
          observation.raw_value,
          observation.context_text,
          observation.extraction_method,
          ...observation.matching_labels,
          ...observation.identity_target_labels,
        ])
        .filter((value): value is string => Boolean(value))
        .join(" ");
      return {
        key,
        kind: group.kind,
        normalizedValue: group.normalizedValue,
        versions,
        sourceLabels,
        roles,
        observations: group.observations,
        searchableText: [
          kindLabel(group.kind),
          group.normalizedValue,
          ...sourceLabels,
          ...roles.map(roleLabel),
          occurrenceText,
        ]
          .join(" ")
          .toLowerCase(),
      };
    })
    .sort(
      (left, right) =>
        right.observations.length - left.observations.length ||
        left.normalizedValue.localeCompare(right.normalizedValue),
    );
}

export default function BibliographicIdentityPanel({ apiHealthy, workspace }: Props) {
  const [lineage, setLineage] = useState<WorkspaceIdentifierLineage | null>(null);
  const [message, setMessage] = useState(
    "Add sources to inspect DOI, arXiv, and ISBN provenance.",
  );
  const [query, setQuery] = useState("");
  const [kindFilter, setKindFilter] = useState<KindFilter>("all");
  const [roleFilter, setRoleFilter] = useState<RoleFilter>("all");
  const [visibleLimit, setVisibleLimit] = useState(INITIAL_IDENTIFIER_LIMIT);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => new Set());

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

  const identifierGroups = useMemo(
    () => buildIdentifierGroups(lineage?.identifiers ?? []),
    [lineage?.identifiers],
  );
  const singleGroupKey = identifierGroups.length === 1 ? identifierGroups[0].key : null;

  useEffect(() => {
    setQuery("");
    setKindFilter("all");
    setRoleFilter("all");
    setVisibleLimit(INITIAL_IDENTIFIER_LIMIT);
    setExpandedGroups(singleGroupKey ? new Set([singleGroupKey]) : new Set());
  }, [lineage?.workspace_id, singleGroupKey]);

  useEffect(() => {
    setVisibleLimit(INITIAL_IDENTIFIER_LIMIT);
  }, [query, kindFilter, roleFilter]);

  const filteredGroups = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return identifierGroups.filter((group) => {
      const kindMatches = kindFilter === "all" || group.kind === kindFilter;
      const roleMatches = roleFilter === "all" || group.roles.includes(roleFilter);
      const queryMatches = !normalizedQuery || group.searchableText.includes(normalizedQuery);
      return kindMatches && roleMatches && queryMatches;
    });
  }, [identifierGroups, kindFilter, query, roleFilter]);

  const crossSourceIdentifierCount = identifierGroups.filter(
    (group) => group.sourceLabels.length > 1,
  ).length;
  const visibleGroups = filteredGroups.slice(0, visibleLimit);

  function toggleGroup(key: string) {
    setExpandedGroups((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

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
            <article><span>Unique identifiers</span><strong>{identifierGroups.length}</strong></article>
            <article data-testid="cross-source-identifier-count"><span>Cross-source identifiers</span><strong>{crossSourceIdentifierCount}</strong></article>
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

          {identifierGroups.length > 0 && (
            <div className="bibliographic-explorer" data-testid="bibliographic-explorer">
              <div className="bibliographic-explorer-heading">
                <div>
                  <strong>Identifier explorer</strong>
                  <span>{identifierGroups.length} unique identifier{identifierGroups.length === 1 ? "" : "s"} from {lineage.summary.observation_count} observation{lineage.summary.observation_count === 1 ? "" : "s"}</span>
                </div>
                <div className="bibliographic-explorer-controls">
                  <input
                    type="search"
                    value={query}
                    data-testid="bibliographic-search-input"
                    placeholder="Search identifier, source, evidence, or method"
                    onChange={(event) => setQuery(event.target.value)}
                  />
                  <select
                    aria-label="Bibliographic identifier kind filter"
                    value={kindFilter}
                    onChange={(event) => setKindFilter(event.target.value as KindFilter)}
                  >
                    <option value="all">All kinds</option>
                    <option value="doi">DOI</option>
                    <option value="arxiv">arXiv</option>
                    <option value="isbn">ISBN</option>
                  </select>
                  <select
                    aria-label="Bibliographic observation role filter"
                    value={roleFilter}
                    onChange={(event) => setRoleFilter(event.target.value as RoleFilter)}
                  >
                    <option value="all">All roles</option>
                    <option value="mention">Source mentions</option>
                    <option value="reference">Reference-linked</option>
                    <option value="source_identity">Source identities</option>
                  </select>
                </div>
              </div>
              <p className="bibliographic-explorer-result-count">
                Showing {Math.min(visibleLimit, filteredGroups.length)} of {filteredGroups.length} matching unique identifier{filteredGroups.length === 1 ? "" : "s"}.
              </p>
            </div>
          )}

          <div className="bibliographic-identity-list">
            {visibleGroups.map((group) => {
              const expanded = expandedGroups.has(group.key);
              const versionLabel = group.versions.length > 0 ? ` · observed v${group.versions.join(", v")}` : "";
              return (
                <section
                  className="bibliographic-identifier-group"
                  key={group.key}
                  data-testid="bibliographic-identifier-group"
                >
                  <button
                    type="button"
                    className="bibliographic-group-toggle"
                    aria-expanded={expanded}
                    onClick={() => toggleGroup(group.key)}
                  >
                    <span className="bibliographic-group-heading">
                      <strong>{kindLabel(group.kind)} · {group.normalizedValue}{versionLabel}</strong>
                      <small>
                        {group.observations.length} observation{group.observations.length === 1 ? "" : "s"} · {group.sourceLabels.length} source{group.sourceLabels.length === 1 ? "" : "s"} · {group.roles.map(roleLabel).join(" · ")}
                      </small>
                    </span>
                    {group.sourceLabels.length > 1 && <span className="bibliographic-shared-badge">Cross-source</span>}
                    <span className="bibliographic-expand-icon" aria-hidden="true">{expanded ? "−" : "+"}</span>
                  </button>
                  <p className="bibliographic-group-sources">Observed in · {group.sourceLabels.join(" · ")}</p>

                  {expanded && (
                    <div className="bibliographic-occurrence-list">
                      {group.observations.map((observation, index) => {
                        const locator = locatorLabel(observation);
                        const target = identityTargetLabel(observation);
                        return (
                          <article
                            key={observation.identifier_id}
                            data-testid="bibliographic-identifier-card"
                          >
                            <div className="bibliographic-occurrence-heading">
                              <strong>Observation {index + 1}</strong>
                              <span>{observation.source_label}</span>
                            </div>
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
                    </div>
                  )}
                </section>
              );
            })}
            {identifierGroups.length === 0 && (
              <p className="bibliographic-identity-empty">
                No explicit DOI, arXiv, or valid ISBN observations were retained from the current workspace sources.
              </p>
            )}
            {identifierGroups.length > 0 && filteredGroups.length === 0 && (
              <p className="bibliographic-identity-empty">No unique identifier matches the current search and filters.</p>
            )}
            {filteredGroups.length > visibleGroups.length && (
              <button
                type="button"
                className="bibliographic-show-more"
                onClick={() => setVisibleLimit((current) => current + INITIAL_IDENTIFIER_LIMIT)}
              >
                Show {Math.min(INITIAL_IDENTIFIER_LIMIT, filteredGroups.length - visibleGroups.length)} more identifiers
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
}
