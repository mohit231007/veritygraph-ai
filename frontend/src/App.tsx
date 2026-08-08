import { useEffect, useState } from "react";

import DocumentWorkspace from "./components/DocumentWorkspace";
import PublicUrlWorkspace from "./components/PublicUrlWorkspace";
import SourcePreview from "./components/SourcePreview";
import WikipediaWorkspace from "./components/WikipediaWorkspace";
import type { HealthResponse, SourceBundle } from "./types";

type ApiState = "checking" | "healthy" | "unavailable";
type SourceMode = "documents" | "wikipedia" | "public-url";

export default function App() {
  const [apiState, setApiState] = useState<ApiState>("checking");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [sourceMode, setSourceMode] = useState<SourceMode>("documents");
  const [bundle, setBundle] = useState<SourceBundle | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function checkApi() {
      try {
        const response = await fetch("/api/v1/health", { signal: controller.signal });
        if (!response.ok) throw new Error(`Health check failed: ${response.status}`);

        const payload = (await response.json()) as HealthResponse;
        setHealth(payload);
        setApiState(payload.status === "healthy" ? "healthy" : "unavailable");
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setApiState("unavailable");
      }
    }

    void checkApi();
    return () => controller.abort();
  }, []);

  function changeMode(mode: SourceMode) {
    setSourceMode(mode);
    setBundle(null);
  }

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">LOCAL-FIRST · EVIDENCE-GROUNDED</p>
        <h1>VerityGraph AI</h1>
        <p className="lede">
          Turn documents and public knowledge into connected intelligence where every future
          relationship, claim and answer can be traced back to its exact evidence.
        </p>
      </header>

      <section className="status-panel" aria-labelledby="system-status-heading">
        <div>
          <p className="section-label" id="system-status-heading">System</p>
          <h2>Local intelligence workspace</h2>
        </div>
        <span className={`status status-${apiState}`} data-testid="api-status">
          {apiState === "checking" && "Checking API…"}
          {apiState === "healthy" && "API healthy"}
          {apiState === "unavailable" && "API unavailable"}
        </span>
        {health && <p className="version">{health.service} · v{health.version}</p>}
      </section>

      <section className="source-studio" aria-labelledby="source-studio-heading">
        <div className="studio-heading">
          <div>
            <p className="section-label">SOURCE STUDIO</p>
            <h2 id="source-studio-heading">Choose how knowledge enters the workspace</h2>
          </div>
          <p>
            Different inputs, one provenance contract. Every source becomes a canonical document
            plus evidence spans before analysis.
          </p>
        </div>

        <div className="mode-switch" role="group" aria-label="Source type">
          <button
            type="button"
            className={sourceMode === "documents" ? "active" : ""}
            aria-pressed={sourceMode === "documents"}
            onClick={() => changeMode("documents")}
          >
            <span>01</span>
            Upload documents
          </button>
          <button
            type="button"
            className={sourceMode === "wikipedia" ? "active" : ""}
            aria-pressed={sourceMode === "wikipedia"}
            data-testid="wikipedia-mode"
            onClick={() => changeMode("wikipedia")}
          >
            <span>02</span>
            Explore Wikipedia
          </button>
          <button
            type="button"
            className={sourceMode === "public-url" ? "active" : ""}
            aria-pressed={sourceMode === "public-url"}
            data-testid="public-url-mode"
            onClick={() => changeMode("public-url")}
          >
            <span>03</span>
            Import public URL
          </button>
        </div>
      </section>

      {sourceMode === "documents" && (
        <DocumentWorkspace apiHealthy={apiState === "healthy"} onBundle={setBundle} />
      )}
      {sourceMode === "wikipedia" && (
        <WikipediaWorkspace apiHealthy={apiState === "healthy"} onBundle={setBundle} />
      )}
      {sourceMode === "public-url" && (
        <PublicUrlWorkspace apiHealthy={apiState === "healthy"} onBundle={setBundle} />
      )}

      {bundle && <SourcePreview bundle={bundle} />}

      <section className="next-grid" aria-label="Product roadmap entry points">
        <article>
          <span>04</span>
          <h3>Persist workspaces</h3>
          <p>SQLite-backed source collections will turn one-off imports into reusable research workspaces.</p>
        </article>
        <article>
          <span>05</span>
          <h3>Build the evidence graph</h3>
          <p>NER, relationship extraction and entity resolution will consume these same spans.</p>
        </article>
        <article>
          <span>06</span>
          <h3>Verify and improve</h3>
          <p>Claim inspection, response ratings, frozen-evidence revisions and version history.</p>
        </article>
      </section>
    </main>
  );
}
