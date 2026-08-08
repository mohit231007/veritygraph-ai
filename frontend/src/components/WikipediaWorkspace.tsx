import { useState } from "react";

import type {
  SourceBundle,
  WikipediaOutline,
  WikipediaSearchResult,
} from "../types";

type RequestState = "idle" | "loading" | "success" | "error";

type Props = {
  apiHealthy: boolean;
  onBundle: (bundle: SourceBundle) => void;
};

export default function WikipediaWorkspace({ apiHealthy, onBundle }: Props) {
  const [query, setQuery] = useState("");
  const [searchState, setSearchState] = useState<RequestState>("idle");
  const [searchError, setSearchError] = useState<string | null>(null);
  const [results, setResults] = useState<WikipediaSearchResult[]>([]);
  const [outline, setOutline] = useState<WikipediaOutline | null>(null);
  const [selectedSections, setSelectedSections] = useState<Set<string>>(new Set(["0"]));
  const [importState, setImportState] = useState<RequestState>("idle");
  const [importMessage, setImportMessage] = useState<string | null>(null);

  async function searchWikipedia() {
    const normalized = query.trim();
    if (normalized.length < 2) return;

    setSearchState("loading");
    setSearchError(null);
    setResults([]);
    setOutline(null);
    setImportState("idle");
    setImportMessage(null);

    try {
      const params = new URLSearchParams({ q: normalized, limit: "6" });
      const response = await fetch(`/api/v1/wikipedia/search?${params.toString()}`);
      const payload = (await response.json()) as WikipediaSearchResult[] | { detail?: string };
      if (!response.ok) {
        const detail = "detail" in payload && payload.detail ? payload.detail : "Search failed.";
        throw new Error(detail);
      }
      const searchResults = payload as WikipediaSearchResult[];
      setResults(searchResults);
      setSearchState("success");
    } catch (error) {
      setSearchError(error instanceof Error ? error.message : "Search failed.");
      setSearchState("error");
    }
  }

  async function inspectPage(result: WikipediaSearchResult) {
    setSearchError(null);
    setOutline(null);
    setSelectedSections(new Set(["0"]));
    setImportState("loading");
    setImportMessage("Loading article sections…");

    try {
      const response = await fetch(`/api/v1/wikipedia/pages/${result.page_id}/outline`);
      const payload = (await response.json()) as WikipediaOutline | { detail?: string };
      if (!response.ok) {
        const detail = "detail" in payload && payload.detail ? payload.detail : "Article preview failed.";
        throw new Error(detail);
      }
      setOutline(payload as WikipediaOutline);
      setImportState("idle");
      setImportMessage(null);
    } catch (error) {
      setImportState("error");
      setImportMessage(error instanceof Error ? error.message : "Article preview failed.");
    }
  }

  function toggleSection(index: string) {
    setSelectedSections((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  async function importSelectedSections() {
    if (!outline || selectedSections.size === 0) return;

    setImportState("loading");
    setImportMessage("Importing selected sections into canonical provenance…");
    try {
      const response = await fetch("/api/v1/wikipedia/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          page_id: outline.page_id,
          section_indices: [...selectedSections],
        }),
      });
      const payload = (await response.json()) as SourceBundle | { detail?: string };
      if (!response.ok) {
        const detail = "detail" in payload && payload.detail ? payload.detail : "Import failed.";
        throw new Error(detail);
      }

      const bundle = payload as SourceBundle;
      setImportState("success");
      setImportMessage(`Ready · ${bundle.spans.length} evidence spans imported.`);
      onBundle(bundle);
    } catch (error) {
      setImportState("error");
      setImportMessage(error instanceof Error ? error.message : "Import failed.");
    }
  }

  return (
    <section className="web-workspace" aria-labelledby="wikipedia-heading">
      <div className="workspace-copy">
        <p className="section-label">PUBLIC KNOWLEDGE</p>
        <h2 id="wikipedia-heading">Explore Wikipedia without leaving VerityGraph</h2>
        <p>
          Search through the official MediaWiki API, inspect an article outline, and import only
          the sections relevant to your analysis. The resulting evidence uses the same canonical
          source model as uploaded documents.
        </p>
      </div>

      <div className="wiki-search-panel">
        <label htmlFor="wikipedia-search">Topic or article</label>
        <div className="search-row">
          <input
            id="wikipedia-search"
            data-testid="wikipedia-search-input"
            type="search"
            value={query}
            placeholder="e.g. NVIDIA, CRISPR, climate finance"
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void searchWikipedia();
            }}
          />
          <button
            type="button"
            onClick={() => void searchWikipedia()}
            disabled={!apiHealthy || query.trim().length < 2 || searchState === "loading"}
          >
            {searchState === "loading" ? "Searching…" : "Search Wikipedia"}
          </button>
        </div>
        <p className="provider-note">Free · official MediaWiki API · no search API key</p>
        {searchState === "error" && <p className="error-message">{searchError}</p>}
      </div>

      {searchState === "success" && (
        <div className="wiki-results" data-testid="wikipedia-results">
          <div className="panel-heading">
            <span>{results.length} results</span>
            <span>Select an article to inspect its sections</span>
          </div>
          {results.length === 0 && <p className="empty-state">No matching Wikipedia pages found.</p>}
          {results.map((result) => (
            <article className="wiki-result" key={result.page_id}>
              <div>
                <h3>{result.title}</h3>
                <p>{result.snippet || "Wikipedia article"}</p>
                <span>{result.word_count.toLocaleString()} words</span>
              </div>
              <button type="button" onClick={() => void inspectPage(result)}>
                Inspect sections
              </button>
            </article>
          ))}
        </div>
      )}

      {outline && (
        <div className="wiki-outline" data-testid="wikipedia-outline">
          <div className="outline-header">
            <div>
              <p className="section-label">ARTICLE OUTLINE</p>
              <h3>{outline.title}</h3>
              <span>Revision {outline.revision_id ?? "current"}</span>
            </div>
            <span>{selectedSections.size} selected</span>
          </div>

          <div className="section-list">
            {outline.sections.map((section) => (
              <label
                className="section-option"
                style={{ paddingLeft: `${Math.min(section.level - 1, 3) * 18 + 12}px` }}
                key={section.index}
              >
                <input
                  type="checkbox"
                  checked={selectedSections.has(section.index)}
                  onChange={() => toggleSection(section.index)}
                />
                <span>
                  <strong>{section.title}</strong>
                  <small>{section.index === "0" ? "Lead section" : `Section ${section.number || section.index}`}</small>
                </span>
              </label>
            ))}
          </div>

          <div className="outline-actions">
            <button
              type="button"
              data-testid="wikipedia-import-button"
              onClick={() => void importSelectedSections()}
              disabled={selectedSections.size === 0 || importState === "loading"}
            >
              {importState === "loading" ? "Building evidence…" : "Analyse selected sections"}
            </button>
            <span aria-live="polite" data-testid="wikipedia-import-status">
              {importMessage}
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
