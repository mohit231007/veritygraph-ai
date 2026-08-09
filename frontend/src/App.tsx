import { useEffect, useState } from "react";

import AnalysisPanel from "./components/AnalysisPanel";
import BibliographicIdentityPanel from "./components/BibliographicIdentityPanel";
import CitationGraphPanel from "./components/CitationGraphPanel";
import ComparisonPanel from "./components/ComparisonPanel";
import DocumentWorkspace from "./components/DocumentWorkspace";
import EvidencePackPanel from "./components/EvidencePackPanel";
import GraphPanel from "./components/GraphPanel";
import PublicUrlWorkspace from "./components/PublicUrlWorkspace";
import ReferenceLineagePanel from "./components/ReferenceLineagePanel";
import RetrievalEvaluationPanel from "./components/RetrievalEvaluationPanel";
import RetrievalPreviewPanel from "./components/RetrievalPreviewPanel";
import SourcePreview from "./components/SourcePreview";
import WikipediaWorkspace from "./components/WikipediaWorkspace";
import WorkspaceManager from "./components/WorkspaceManager";
import type {
  HealthResponse,
  SourceBundle,
  WorkspaceAnalysis,
  WorkspaceDetail,
} from "./types";

type ApiState = "checking" | "healthy" | "unavailable";
type SourceMode = "documents" | "wikipedia" | "public-url";

export default function App() {
  const [apiState, setApiState] = useState<ApiState>("checking");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [sourceMode, setSourceMode] = useState<SourceMode>("documents");
  const [bundle, setBundle] = useState<SourceBundle | null>(null);
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceDetail | null>(null);
  const [activeAnalysis, setActiveAnalysis] = useState<WorkspaceAnalysis | null>(null);
  const [workspaceRefreshToken, setWorkspaceRefreshToken] = useState(0);
  const [handoffBusy, setHandoffBusy] = useState(false);
  const [handoffMessage, setHandoffMessage] = useState<string | null>(null);

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

  useEffect(() => {
    setHandoffMessage(null);
  }, [bundle?.document.source_id]);

  function changeMode(mode: SourceMode) {
    setSourceMode(mode);
    setBundle(null);
  }

  const currentSource = bundle?.document ?? null;
  const currentSourceSaved =
    Boolean(currentSource) &&
    Boolean(
      activeWorkspace?.sources.some((source) => source.source_id === currentSource?.source_id),
    );

  async function addImportedSourceToWorkspace() {
    if (!activeWorkspace || !currentSource) return;
    setHandoffBusy(true);
    setHandoffMessage(null);
    try {
      const response = await fetch(
        `/api/v1/workspaces/${activeWorkspace.workspace_id}/sources/${currentSource.source_id}`,
        { method: "PUT" },
      );
      const payload = (await response.json()) as WorkspaceDetail | { detail?: string };
      if (!response.ok) {
        throw new Error(
          "detail" in payload ? payload.detail ?? "Could not add source." : "Could not add source.",
        );
      }
      const updated = payload as WorkspaceDetail;
      setActiveWorkspace(updated);
      setWorkspaceRefreshToken((current) => current + 1);
      setHandoffMessage(`Saved “${currentSource.filename ?? currentSource.title}” in ${updated.name}.`);
    } catch (error) {
      setHandoffMessage(error instanceof Error ? error.message : "Could not add source.");
    } finally {
      setHandoffBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">LOCAL-FIRST · EVIDENCE-GROUNDED</p>
        <h1>VerityGraph AI</h1>
        <p className="lede">
          Turn documents and public knowledge into connected intelligence where relationships,
          retrieval results and evidence packs remain traceable to their exact source spans.
        </p>
      </header>

      <section className="status-panel" aria-labelledby="system-status-heading">
        <div>
          <p className="section-label" id="system-status-heading">System</p>
          <h2>Evidence intelligence workspace</h2>
        </div>
        <span className={`status status-${apiState}`} data-testid="api-status">
          {apiState === "checking" && "Checking API…"}
          {apiState === "healthy" && "API healthy"}
          {apiState === "unavailable" && "API unavailable"}
        </span>
        {health && <p className="version">{health.service} · v{health.version}</p>}
      </section>

      <WorkspaceManager
        apiHealthy={apiState === "healthy"}
        currentSource={currentSource}
        onWorkspaceChange={setActiveWorkspace}
        refreshToken={workspaceRefreshToken}
      />

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

      {currentSource && (
        <section
          className={`source-workspace-handoff${currentSourceSaved ? " saved" : ""}`}
          data-testid="source-workspace-handoff"
          aria-labelledby="source-workspace-handoff-heading"
        >
          <div>
            <p className="section-label">WORKSPACE HANDOFF</p>
            <h2 id="source-workspace-handoff-heading">
              {currentSourceSaved
                ? "Source is ready for workspace intelligence"
                : "Keep the imported source with your research"}
            </h2>
            <p>
              {activeWorkspace
                ? currentSourceSaved
                  ? `“${currentSource.filename ?? currentSource.title}” is saved in ${activeWorkspace.name}. Retrieval, analysis, comparison and graph views can now use it.`
                  : `“${currentSource.filename ?? currentSource.title}” is imported but not yet part of ${activeWorkspace.name}. Add it once to make its spans available to workspace intelligence.`
                : "Create or select a workspace above, then add this imported source to make it available to workspace intelligence."}
            </p>
            {handoffMessage && <span className="source-handoff-message">{handoffMessage}</span>}
          </div>
          {activeWorkspace && (
            <button
              type="button"
              data-testid="source-workspace-save-button"
              disabled={handoffBusy || currentSourceSaved}
              onClick={() => void addImportedSourceToWorkspace()}
            >
              {handoffBusy
                ? "Adding…"
                : currentSourceSaved
                  ? `Saved in ${activeWorkspace.name}`
                  : `Add to ${activeWorkspace.name}`}
            </button>
          )}
        </section>
      )}

      <section className="intelligence-divider" aria-labelledby="intelligence-divider-heading">
        <p className="section-label">WORKSPACE INTELLIGENCE</p>
        <h2 id="intelligence-divider-heading">Inspect what the saved evidence supports</h2>
        <p>
          The panels below operate on sources saved in the active workspace, not merely on the last
          source previewed in Source Studio.
        </p>
      </section>

      <ReferenceLineagePanel apiHealthy={apiState === "healthy"} workspace={activeWorkspace} />

      <BibliographicIdentityPanel apiHealthy={apiState === "healthy"} workspace={activeWorkspace} />

      <CitationGraphPanel apiHealthy={apiState === "healthy"} workspace={activeWorkspace} />

      <RetrievalPreviewPanel apiHealthy={apiState === "healthy"} workspace={activeWorkspace} />

      <EvidencePackPanel apiHealthy={apiState === "healthy"} workspace={activeWorkspace} />

      <RetrievalEvaluationPanel apiHealthy={apiState === "healthy"} workspace={activeWorkspace} />

      <AnalysisPanel
        apiHealthy={apiState === "healthy"}
        workspace={activeWorkspace}
        onAnalysisChange={setActiveAnalysis}
      />

      <GraphPanel
        apiHealthy={apiState === "healthy"}
        workspace={activeWorkspace}
        analysis={activeAnalysis}
      />

      <ComparisonPanel
        apiHealthy={apiState === "healthy"}
        workspace={activeWorkspace}
        analysis={activeAnalysis}
      />

      <section className="next-grid" aria-label="Product capabilities">
        <article>
          <span>04</span>
          <h3>Analyse the workspace</h3>
          <p>Local extraction and conservative entity resolution retain exact evidence lineage.</p>
        </article>
        <article>
          <span>05</span>
          <h3>Explore, retrieve and compare</h3>
          <p>Graph analytics, citation topology and measured retrieval remain inspectable.</p>
        </article>
        <article>
          <span>06</span>
          <h3>Package grounded evidence</h3>
          <p>Budgeted evidence packs preserve exact span and excerpt ranges for downstream use.</p>
        </article>
      </section>
    </main>
  );
}
