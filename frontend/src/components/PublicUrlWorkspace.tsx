import { useState } from "react";

import "../source-studio.css";
import type { SourceBundle } from "../types";

type RequestState = "idle" | "loading" | "success" | "error";

type Props = {
  apiHealthy: boolean;
  onBundle: (bundle: SourceBundle) => void;
};

export default function PublicUrlWorkspace({ apiHealthy, onBundle }: Props) {
  const [url, setUrl] = useState("");
  const [state, setState] = useState<RequestState>("idle");
  const [message, setMessage] = useState<string | null>(null);

  async function importUrl() {
    const normalized = url.trim();
    if (normalized.length < 8) return;

    setState("loading");
    setMessage("Validating target, fetching bounded content, and extracting main evidence…");

    try {
      const response = await fetch("/api/v1/web/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: normalized }),
      });
      const payload = (await response.json()) as SourceBundle | { detail?: string };
      if (!response.ok) {
        const detail = "detail" in payload && payload.detail ? payload.detail : "Import failed.";
        throw new Error(detail);
      }

      const bundle = payload as SourceBundle;
      setState("success");
      setMessage(`Ready · ${bundle.spans.length} evidence spans extracted from the public page.`);
      onBundle(bundle);
    } catch (error) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "Import failed.");
    }
  }

  return (
    <section className="web-workspace" aria-labelledby="public-url-heading">
      <div className="workspace-copy">
        <p className="section-label">PUBLIC URL INTELLIGENCE</p>
        <h2 id="public-url-heading">Import a permitted public page safely</h2>
        <p>
          Paste a public HTTP(S) page. VerityGraph validates the network target and every
          redirect, bounds the response, extracts the page's main readable content, and then
          creates the same evidence contract used by documents and Wikipedia.
        </p>
      </div>

      <div className="public-url-panel">
        <label htmlFor="public-url">Public page URL</label>
        <div className="search-row">
          <input
            id="public-url"
            data-testid="public-url-input"
            type="url"
            value={url}
            placeholder="https://example.com/research/article"
            onChange={(event) => {
              setUrl(event.target.value);
              if (state !== "loading") {
                setState("idle");
                setMessage(null);
              }
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") void importUrl();
            }}
          />
          <button
            type="button"
            data-testid="public-url-import-button"
            onClick={() => void importUrl()}
            disabled={!apiHealthy || url.trim().length < 8 || state === "loading"}
          >
            {state === "loading" ? "Fetching safely…" : "Fetch & analyse"}
          </button>
        </div>

        <div className="safety-grid" aria-label="Public URL safety controls">
          <span>HTTP(S) only</span>
          <span>Private/internal IPs blocked</span>
          <span>Redirects revalidated</span>
          <span>3 MB response limit</span>
          <span>HTML/XHTML/TXT only</span>
          <span>No auth or paywall bypass</span>
        </div>

        <p
          className={state === "error" ? "error-message" : "provider-note"}
          aria-live="polite"
          data-testid="public-url-status"
        >
          {message ?? "The server fetches only explicitly supplied, permitted public pages."}
        </p>
      </div>
    </section>
  );
}
