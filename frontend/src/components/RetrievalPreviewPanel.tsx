import { FormEvent, useEffect, useState } from "react";

import "../retrieval-preview.css";
import type { WorkspaceDetail } from "../types";

type CitationMechanism = "url_reference" | "bibliographic_identifier";
type CitationDirection = "outgoing" | "incoming";

type RetrievalHit = {
  rank: number;
  source_id: string;
  source_label: string;
  span_id: string;
  text: string;
  page_number: number | null;
  section: string | null;
  paragraph_number: number | null;
  char_start: number;
  char_end: number;
  score: number;
  matched_terms: string[];
};

type CitationContext = {
  edge_id: string;
  seed_source_id: string;
  seed_source_label: string;
  direction: CitationDirection;
  neighbor_source_id: string;
  neighbor_label: string;
  mechanisms: CitationMechanism[];
  evidence_count: number;
};

type RetrievalPreview = {
  workspace_id: string;
  retrieval_version: string;
  query: string;
  summary: {
    workspace_source_count: number;
    indexed_span_count: number;
    query_term_count: number;
    direct_hit_count: number;
    direct_hit_source_count: number;
    citation_context_count: number;
  };
  hits: RetrievalHit[];
  citation_context: CitationContext[];
  interpretation_note: string;
};

type Props = {
  apiHealthy: boolean;
  workspace: WorkspaceDetail | null;
};

function locationLabel(hit: RetrievalHit) {
  const parts: string[] = [];
  if (hit.page_number !== null) parts.push(`Page ${hit.page_number}`);
  if (hit.section) parts.push(hit.section);
  if (hit.paragraph_number !== null) parts.push(`Paragraph ${hit.paragraph_number}`);
  parts.push(hit.span_id);
  return parts.join(" · ");
}

function mechanismLabel(mechanisms: CitationMechanism[]) {
  if (mechanisms.length === 2) return "URL + bibliographic ID";
  return mechanisms[0] === "bibliographic_identifier" ? "Bibliographic ID" : "URL reference";
}

export default function RetrievalPreviewPanel({ apiHealthy, workspace }: Props) {
  const [query, setQuery] = useState("");
  const [preview, setPreview] = useState<RetrievalPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(
    "Search persisted evidence spans without embeddings or an LLM.",
  );

  useEffect(() => {
    setPreview(null);
    setMessage("Search persisted evidence spans without embeddings or an LLM.");
  }, [workspace?.workspace_id]);

  async function runPreview(event: FormEvent) {
    event.preventDefault();
    if (!apiHealthy || !workspace || query.trim().length < 2) return;

    setLoading(true);
    setMessage("Ranking local evidence spans…");
    try {
      const response = await fetch(
        `/api/v1/workspaces/${workspace.workspace_id}/retrieval/preview`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: query.trim(), limit: 8 }),
        },
      );
      if (!response.ok) throw new Error("Could not build retrieval preview.");
      const payload = (await response.json()) as RetrievalPreview;
      setPreview(payload);
      setMessage(
        `Retrieval ready · ${payload.summary.direct_hit_count} ranked span${payload.summary.direct_hit_count === 1 ? "" : "s"} from ${payload.summary.direct_hit_source_count} source${payload.summary.direct_hit_source_count === 1 ? "" : "s"} · ${payload.summary.citation_context_count} citation context item${payload.summary.citation_context_count === 1 ? "" : "s"}`,
      );
    } catch (error) {
      setPreview(null);
      setMessage(error instanceof Error ? error.message : "Could not build retrieval preview.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section
      className="retrieval-preview-panel"
      aria-labelledby="retrieval-preview-heading"
      data-testid="retrieval-preview-panel"
    >
      <div className="retrieval-preview-heading">
        <div>
          <p className="section-label">GROUNDED RETRIEVAL PREVIEW</p>
          <h2 id="retrieval-preview-heading">Rank evidence first, expand provenance second</h2>
        </div>
        {preview && <span>{preview.retrieval_version}</span>}
      </div>

      <form className="retrieval-search" onSubmit={runPreview}>
        <label htmlFor="retrieval-query">Question or evidence keywords</label>
        <div>
          <input
            id="retrieval-query"
            data-testid="retrieval-query-input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. accelerated networking evidence"
            disabled={!apiHealthy || !workspace || loading}
          />
          <button
            type="submit"
            data-testid="retrieval-search-button"
            disabled={!apiHealthy || !workspace || loading || query.trim().length < 2}
          >
            {loading ? "Ranking…" : "Preview retrieval"}
          </button>
        </div>
      </form>

      <p className="retrieval-preview-status" aria-live="polite" data-testid="retrieval-preview-status">
        {message}
      </p>

      {preview && (
        <>
          <div className="retrieval-preview-metrics">
            <article><span>Workspace sources</span><strong>{preview.summary.workspace_source_count}</strong></article>
            <article><span>Indexed spans</span><strong>{preview.summary.indexed_span_count}</strong></article>
            <article data-testid="retrieval-hit-count"><span>Ranked spans</span><strong>{preview.summary.direct_hit_count}</strong></article>
            <article><span>Direct-hit sources</span><strong>{preview.summary.direct_hit_source_count}</strong></article>
            <article data-testid="retrieval-context-count"><span>Citation context</span><strong>{preview.summary.citation_context_count}</strong></article>
          </div>

          <aside className="retrieval-preview-guardrail" data-testid="retrieval-preview-guardrail">
            <strong>Citation neighbor ≠ retrieved evidence or query support.</strong>
            <p>{preview.interpretation_note}</p>
          </aside>

          <div className="retrieval-results-grid">
            <section aria-labelledby="ranked-evidence-heading">
              <h3 id="ranked-evidence-heading">Ranked evidence spans</h3>
              <div className="retrieval-hit-list" data-testid="retrieval-hit-list">
                {preview.hits.map((hit) => (
                  <article key={hit.span_id} data-testid="retrieval-hit-card">
                    <header>
                      <strong>#{hit.rank} · {hit.source_label}</strong>
                      <span>BM25 {hit.score.toFixed(3)}</span>
                    </header>
                    <p className="retrieval-location">{locationLabel(hit)}</p>
                    <blockquote>“{hit.text}”</blockquote>
                    <footer>Matched · {hit.matched_terms.join(" · ")}</footer>
                  </article>
                ))}
                {preview.hits.length === 0 && (
                  <p className="retrieval-empty">No persisted span matched the lexical query.</p>
                )}
              </div>
            </section>

            <section aria-labelledby="citation-context-heading">
              <h3 id="citation-context-heading">Citation discovery context — not ranked evidence</h3>
              <div className="retrieval-context-list" data-testid="retrieval-context-list">
                {preview.citation_context.map((context) => (
                  <article
                    key={`${context.edge_id}-${context.seed_source_id}-${context.direction}`}
                    data-testid="retrieval-context-card"
                  >
                    <strong>{context.seed_source_label}</strong>
                    <p>
                      {context.direction === "outgoing" ? "cites / references" : "is cited / referenced by"}
                      {" "}<strong>{context.neighbor_label}</strong>
                    </p>
                    <footer>{mechanismLabel(context.mechanisms)} · {context.evidence_count} explicit evidence item{context.evidence_count === 1 ? "" : "s"}</footer>
                  </article>
                ))}
                {preview.citation_context.length === 0 && (
                  <p className="retrieval-empty">No uniquely resolved citation neighbor is attached to the directly matched sources.</p>
                )}
              </div>
            </section>
          </div>
        </>
      )}
    </section>
  );
}
