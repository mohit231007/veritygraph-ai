import { useEffect, useMemo, useState } from "react";

import "../workspace.css";
import type { SourceDocument, WorkspaceDetail, WorkspaceSummary } from "../types";

const ACTIVE_WORKSPACE_STORAGE_KEY = "veritygraph.activeWorkspaceId";

type Props = {
  apiHealthy: boolean;
  currentSource: SourceDocument | null;
  onWorkspaceChange: (workspace: WorkspaceDetail | null) => void;
  refreshToken?: number;
};

export default function WorkspaceManager({
  apiHealthy,
  currentSource,
  onWorkspaceChange,
  refreshToken = 0,
}: Props) {
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [activeId, setActiveId] = useState<string>(
    () => window.localStorage.getItem(ACTIVE_WORKSPACE_STORAGE_KEY) ?? "",
  );
  const [detail, setDetail] = useState<WorkspaceDetail | null>(null);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const currentSourceSaved = useMemo(
    () => detail?.sources.some((source) => source.source_id === currentSource?.source_id) ?? false,
    [detail, currentSource],
  );

  async function loadWorkspaces(preferredId?: string) {
    const response = await fetch("/api/v1/workspaces");
    if (!response.ok) throw new Error("Could not load persistent workspaces.");
    const payload = (await response.json()) as WorkspaceSummary[];
    setWorkspaces(payload);

    const nextId =
      preferredId && payload.some((workspace) => workspace.workspace_id === preferredId)
        ? preferredId
        : activeId && payload.some((workspace) => workspace.workspace_id === activeId)
          ? activeId
          : payload[0]?.workspace_id ?? "";
    setActiveId(nextId);
    if (!nextId) setDetail(null);
  }

  async function loadDetail(workspaceId: string) {
    if (!workspaceId) {
      setDetail(null);
      return;
    }
    const response = await fetch(`/api/v1/workspaces/${workspaceId}`);
    if (!response.ok) throw new Error("Could not load workspace details.");
    setDetail((await response.json()) as WorkspaceDetail);
  }

  useEffect(() => {
    onWorkspaceChange(detail);
  }, [detail, onWorkspaceChange]);

  useEffect(() => {
    if (activeId) {
      window.localStorage.setItem(ACTIVE_WORKSPACE_STORAGE_KEY, activeId);
    } else {
      window.localStorage.removeItem(ACTIVE_WORKSPACE_STORAGE_KEY);
    }
  }, [activeId]);

  useEffect(() => {
    if (!apiHealthy) return;
    void loadWorkspaces().catch((error: unknown) => {
      setMessage(error instanceof Error ? error.message : "Could not load workspaces.");
    });
    // The initial API-health transition is the only automatic list refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiHealthy]);

  useEffect(() => {
    if (!apiHealthy || !activeId) return;
    void loadDetail(activeId).catch((error: unknown) => {
      setMessage(error instanceof Error ? error.message : "Could not load workspace details.");
    });
  }, [activeId, apiHealthy, refreshToken]);

  async function createWorkspace() {
    const name = newName.trim();
    if (name.length < 2) return;
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch("/api/v1/workspaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const created = (await response.json()) as WorkspaceDetail | { detail?: string };
      if (!response.ok) {
        throw new Error("detail" in created ? created.detail ?? "Create failed." : "Create failed.");
      }
      const workspace = created as WorkspaceDetail;
      setNewName("");
      setDetail(workspace);
      await loadWorkspaces(workspace.workspace_id);
      setMessage(`Workspace “${workspace.name}” created locally.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Create failed.");
    } finally {
      setBusy(false);
    }
  }

  async function addCurrentSource() {
    if (!detail || !currentSource) return;
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(
        `/api/v1/workspaces/${detail.workspace_id}/sources/${currentSource.source_id}`,
        { method: "PUT" },
      );
      if (!response.ok) throw new Error("Could not add source to workspace.");
      const updated = (await response.json()) as WorkspaceDetail;
      setDetail(updated);
      await loadWorkspaces(updated.workspace_id);
      setMessage(`Added “${currentSource.title}” to ${updated.name}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not add source.");
    } finally {
      setBusy(false);
    }
  }

  async function removeSource(sourceId: string) {
    if (!detail) return;
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(
        `/api/v1/workspaces/${detail.workspace_id}/sources/${sourceId}`,
        { method: "DELETE" },
      );
      if (!response.ok) throw new Error("Could not remove source from workspace.");
      const updated = (await response.json()) as WorkspaceDetail;
      setDetail(updated);
      await loadWorkspaces(updated.workspace_id);
      setMessage("Source removed from this workspace. The canonical source remains stored.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not remove source.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteWorkspace() {
    if (!detail) return;
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(`/api/v1/workspaces/${detail.workspace_id}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Could not delete workspace.");
      setDetail(null);
      setActiveId("");
      await loadWorkspaces();
      setMessage("Workspace deleted. Its canonical sources remain available.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not delete workspace.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="workspace-manager" aria-labelledby="workspace-manager-heading">
      <div className="workspace-manager-heading">
        <div>
          <p className="section-label">RESEARCH WORKSPACES</p>
          <h2 id="workspace-manager-heading">Persistent multi-source intelligence</h2>
        </div>
        <span className="persistence-badge">SQLite · local</span>
      </div>

      <div className="workspace-controls">
        <label>
          Active workspace
          <select
            data-testid="workspace-select"
            value={activeId}
            disabled={!apiHealthy || busy || workspaces.length === 0}
            onChange={(event) => setActiveId(event.target.value)}
          >
            {workspaces.length === 0 && <option value="">No workspaces yet</option>}
            {workspaces.map((workspace) => (
              <option key={workspace.workspace_id} value={workspace.workspace_id}>
                {workspace.name} · {workspace.source_count} sources
              </option>
            ))}
          </select>
        </label>

        <div className="workspace-create">
          <label htmlFor="workspace-name">New workspace</label>
          <div>
            <input
              id="workspace-name"
              data-testid="workspace-name-input"
              value={newName}
              placeholder="e.g. NVIDIA research"
              maxLength={100}
              onChange={(event) => setNewName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void createWorkspace();
              }}
            />
            <button
              type="button"
              data-testid="workspace-create-button"
              disabled={!apiHealthy || busy || newName.trim().length < 2}
              onClick={() => void createWorkspace()}
            >
              Create
            </button>
          </div>
        </div>
      </div>

      {detail && (
        <div className="workspace-detail" data-testid="workspace-detail">
          <div className="workspace-detail-header">
            <div>
              <strong>{detail.name}</strong>
              <span data-testid="workspace-source-count">
                {detail.source_count} {detail.source_count === 1 ? "source" : "sources"}
              </span>
            </div>
            <button type="button" className="danger-link" disabled={busy} onClick={() => void deleteWorkspace()}>
              Delete workspace
            </button>
          </div>

          {currentSource && (
            <div className="current-source-action" data-testid="workspace-current-source">
              <div>
                <span>Current analysed source</span>
                <strong>{currentSource.filename ?? currentSource.title}</strong>
              </div>
              <button
                type="button"
                data-testid="workspace-add-source"
                disabled={busy || currentSourceSaved}
                onClick={() => void addCurrentSource()}
              >
                {currentSourceSaved ? "Saved in workspace" : "Add current source"}
              </button>
            </div>
          )}

          <div className="workspace-source-list" data-testid="workspace-source-list">
            {detail.sources.length === 0 && (
              <p className="workspace-empty">Import evidence below, then add it to this workspace.</p>
            )}
            {detail.sources.map((source) => (
              <article key={source.source_id} data-source-id={source.source_id}>
                <div>
                  <span>{source.source_type.replaceAll("_", " ")}</span>
                  <strong>{source.filename ?? source.title}</strong>
                </div>
                <button type="button" disabled={busy} onClick={() => void removeSource(source.source_id)}>
                  Remove
                </button>
              </article>
            ))}
          </div>
        </div>
      )}

      <p className="workspace-message" aria-live="polite" data-testid="workspace-message">
        {message ?? "Sources and workspace membership persist locally across browser sessions."}
      </p>
    </section>
  );
}
