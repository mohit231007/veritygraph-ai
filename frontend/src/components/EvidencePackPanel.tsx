import { FormEvent, useEffect, useMemo, useState } from "react";

import "../evidence-pack.css";
import type { WorkspaceDetail } from "../types";

type CitationContext = {
  edge_id: string;
  seed_source_id: string;
  seed_source_label: string;
  direction: "outgoing" | "incoming";
  neighbor_source_id: string;
  neighbor_label: string;
  mechanisms: ("url_reference" | "bibliographic_identifier")[];
  evidence_count: number;
};

type EvidenceExcerpt = {
  rank: number;
  source_id: string;
  source_label: string;
  span_id: string;
  page_number: number | null;
  section: string | null;
  paragraph_number: number | null;
  span_char_start: number;
  span_char_end: number;
  excerpt_char_start: number;
  excerpt_char_end: number;
  text: string;
  score: number;
  matched_terms: string[];
  truncated_before: boolean;
  truncated_after: boolean;
};

type EvidencePack = {
  workspace_id: string;
  pack_version: string;
  retrieval_version: string;
  query: string;
  summary: {
    workspace_source_count: number;
    indexed_span_count: number;
    candidate_hit_count: number;
    selected_excerpt_count: number;
    selected_source_count: number;
    selected_char_count: number;
    skipped_by_source_cap: number;
    skipped_by_budget: number;
    citation_context_count: number;
  };
  excerpts: EvidenceExcerpt[];
  citation_context: CitationContext[];
  interpretation_note: string;
};

type Props = {
  apiHealthy: boolean;
  workspace: WorkspaceDetail | null;
};

function locationLabel(excerpt: EvidenceExcerpt) {
  const parts: string[] = [];
  if (excerpt.page_number !== null) parts.push(`Page ${excerpt.page_number}`);
  if (excerpt.section) parts.push(excerpt.section);
  if (excerpt.paragraph_number !== null) parts.push(`Paragraph ${excerpt.paragraph_number}`);
  parts.push(excerpt.span_id);
  return parts.join(" · ");
}

function evidenceBlock(pack: EvidencePack) {
  const header = [
    `QUERY: ${pack.query}`,
    `PACK: ${pack.pack_version}`,
    "RULE: Use only the excerpts below as direct evidence. Citation context is discovery metadata only.",
    "",
  ];
  const excerpts = pack.excerpts.flatMap((excerpt, index) => [
    `[E${index + 1}] ${excerpt.source_label} | ${excerpt.span_id} | chars ${excerpt.excerpt_char_start}-${excerpt.excerpt_char_end}`,
    excerpt.text,
    "",
  ]);
  return [...header, ...excerpts].join("\n");
}

export default function EvidencePackPanel({ apiHealthy, workspace }: Props) {
  const [query, setQuery] = useState("");
  const [maxExcerpts, setMaxExcerpts] = useState(8);
  const [maxPerSource, setMaxPerSource] = useState(3);
  const [maxCharsPerExcerpt, setMaxCharsPerExcerpt] = useState(1200);
  const [maxTotalChars, setMaxTotalChars] = useState(6000);
  const [pack, setPack] = useState<EvidencePack | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(
    "Build a bounded, generator-ready packet from directly retrieved evidence only.",
  );

  useEffect(() => {
    setPack(null);
    setMessage("Build a bounded, generator-ready packet from directly retrieved evidence only.");
  }, [workspace?.workspace_id]);

  const block = useMemo(() => (pack ? evidenceBlock(pack) : ""), [pack]);

  async function buildPack(event: FormEvent) {
    event.preventDefault();
    if (!apiHealthy || !workspace || query.trim().length < 2) return;

    setLoading(true);
    setMessage("Ranking spans and assembling a provenance-safe evidence budget…");
    try {
      const response = await fetch(
        `/api/v1/workspaces/${workspace.workspace_id}/retrieval/evidence-pack`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: query.trim(),
            max_excerpts: maxExcerpts,
            max_excerpts_per_source: maxPerSource,
            max_chars_per_excerpt: maxCharsPerExcerpt,
            max_total_chars: maxTotalChars,
          }),
        },
      );
      const payload = (await response.json()) as EvidencePack | { detail?: string };
      if (!response.ok) {
        throw new Error("detail" in payload ? payload.detail ?? "Evidence pack failed." : "Evidence pack failed.");
      }
      const result = payload as EvidencePack;
      setPack(result);
      setMessage(
        `Pack ready · ${result.summary.selected_excerpt_count} excerpt${result.summary.selected_excerpt_count === 1 ? "" : "s"} · ${result.summary.selected_source_count} source${result.summary.selected_source_count === 1 ? "" : "s"} · ${result.summary.selected_char_count} characters`,
      );
    } catch (error) {
      setPack(null);
      setMessage(error instanceof Error ? error.message : "Evidence pack failed.");
    } finally {
      setLoading(false);
    }
  }

  async function copyPack() {
    if (!pack) return;
    await navigator.clipboard.writeText(block);
    setMessage("Evidence block copied with source/span provenance.");
  }

  function downloadPack() {
    if (!pack) return;
    const blob = new Blob([JSON.stringify(pack, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `veritygraph-evidence-pack-${pack.workspace_id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="evidence-pack-panel" aria-labelledby="evidence-pack-heading" data-testid="evidence-pack-panel">
      <div className="evidence-pack-heading">
        <div>
          <p className="section-label">GROUNDED EVIDENCE PACK</p>
          <h2 id="evidence-pack-heading">Build the exact context a future answer is allowed to use</h2>
        </div>
        {pack && <span>{pack.pack_version}</span>}
      </div>

      <form className="evidence-pack-form" onSubmit={buildPack}>
        <label htmlFor="evidence-pack-query">Question or evidence keywords</label>
        <div className="evidence-pack-query-row">
          <input
            id="evidence-pack-query"
            data-testid="evidence-pack-query-input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. accelerated networking evidence"
            disabled={!apiHealthy || !workspace || loading}
          />
          <button
            type="submit"
            data-testid="evidence-pack-build-button"
            disabled={!apiHealthy || !workspace || loading || query.trim().length < 2}
          >
            {loading ? "Building…" : "Build evidence pack"}
          </button>
        </div>

        <div className="evidence-pack-budget-grid">
          <label>
            Max excerpts
            <input type="number" min={1} max={20} value={maxExcerpts} onChange={(event) => setMaxExcerpts(Number(event.target.value))} />
          </label>
          <label>
            Per source
            <input type="number" min={1} max={10} value={maxPerSource} onChange={(event) => setMaxPerSource(Number(event.target.value))} />
          </label>
          <label>
            Chars / excerpt
            <input type="number" min={120} max={5000} value={maxCharsPerExcerpt} onChange={(event) => setMaxCharsPerExcerpt(Number(event.target.value))} />
          </label>
          <label>
            Total chars
            <input type="number" min={500} max={30000} value={maxTotalChars} onChange={(event) => setMaxTotalChars(Number(event.target.value))} />
          </label>
        </div>
      </form>

      <p className="evidence-pack-status" aria-live="polite" data-testid="evidence-pack-status">{message}</p>

      {pack && (
        <>
          <div className="evidence-pack-metrics">
            <article data-testid="evidence-pack-excerpt-count"><span>Excerpts</span><strong>{pack.summary.selected_excerpt_count}</strong></article>
            <article><span>Sources</span><strong>{pack.summary.selected_source_count}</strong></article>
            <article><span>Characters</span><strong>{pack.summary.selected_char_count}</strong></article>
            <article data-testid="evidence-pack-context-count"><span>Citation context</span><strong>{pack.summary.citation_context_count}</strong></article>
          </div>

          <aside className="evidence-pack-guardrail" data-testid="evidence-pack-guardrail">
            <strong>Citation neighbor text is not generator evidence unless independently retrieved.</strong>
            <p>{pack.interpretation_note}</p>
          </aside>

          <div className="evidence-pack-actions">
            <button type="button" onClick={copyPack} data-testid="evidence-pack-copy-button">Copy evidence block</button>
            <button type="button" onClick={downloadPack}>Download JSON</button>
          </div>

          <div className="evidence-pack-grid">
            <section aria-labelledby="evidence-pack-excerpts-heading">
              <h3 id="evidence-pack-excerpts-heading">Allowed evidence excerpts</h3>
              <div className="evidence-pack-excerpts" data-testid="evidence-pack-excerpts">
                {pack.excerpts.map((excerpt, index) => (
                  <article key={excerpt.span_id} data-testid="evidence-pack-excerpt">
                    <header>
                      <strong>[E{index + 1}] #{excerpt.rank} · {excerpt.source_label}</strong>
                      <span>BM25 {excerpt.score.toFixed(3)}</span>
                    </header>
                    <p className="evidence-pack-location">{locationLabel(excerpt)}</p>
                    <p className="evidence-pack-offsets">
                      Excerpt chars {excerpt.excerpt_char_start}–{excerpt.excerpt_char_end} inside span {excerpt.span_char_start}–{excerpt.span_char_end}
                    </p>
                    <blockquote>{excerpt.truncated_before ? "…" : ""}{excerpt.text}{excerpt.truncated_after ? "…" : ""}</blockquote>
                    <footer>Matched · {excerpt.matched_terms.join(" · ")}</footer>
                  </article>
                ))}
                {pack.excerpts.length === 0 && <p className="evidence-pack-empty">No directly retrieved span matched this query.</p>}
              </div>
            </section>

            <section aria-labelledby="evidence-pack-context-heading">
              <h3 id="evidence-pack-context-heading">Citation discovery context — metadata only</h3>
              <div className="evidence-pack-context" data-testid="evidence-pack-context">
                {pack.citation_context.map((item) => (
                  <article key={`${item.edge_id}-${item.seed_source_id}-${item.direction}`} data-testid="evidence-pack-context-item">
                    <strong>{item.seed_source_label}</strong>
                    <p>{item.direction === "outgoing" ? "cites / references" : "is cited / referenced by"} <strong>{item.neighbor_label}</strong></p>
                    <footer>{item.mechanisms.join(" + ").replaceAll("_", " ")} · {item.evidence_count} explicit provenance item{item.evidence_count === 1 ? "" : "s"}</footer>
                  </article>
                ))}
                {pack.citation_context.length === 0 && <p className="evidence-pack-empty">No citation context is attached to the selected direct-evidence sources.</p>}
              </div>
            </section>
          </div>
        </>
      )}
    </section>
  );
}
