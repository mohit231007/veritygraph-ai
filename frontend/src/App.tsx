import { useEffect, useState } from "react";

type ApiState = "checking" | "healthy" | "unavailable";
type UploadState = "idle" | "uploading" | "success" | "error";

type HealthResponse = {
  status: string;
  service: string;
  version: string;
};

type SourceDocument = {
  source_id: string;
  source_type: string;
  title: string;
  filename: string | null;
  source_format: string;
  mime_type: string;
  content_hash: string;
  size_bytes: number;
  metadata: Record<string, string | number | boolean | null>;
};

type SourceSpan = {
  span_id: string;
  source_id: string;
  text: string;
  page_number: number | null;
  section: string | null;
  paragraph_number: number | null;
  char_start: number;
  char_end: number;
};

type SourceBundle = {
  document: SourceDocument;
  spans: SourceSpan[];
};

function spanLocation(span: SourceSpan) {
  const parts: string[] = [];
  if (span.page_number) parts.push(`Page ${span.page_number}`);
  if (span.paragraph_number) parts.push(`Paragraph ${span.paragraph_number}`);
  if (span.section) parts.push(span.section.replaceAll("_", " "));
  return parts.length > 0 ? parts.join(" · ") : "Document span";
}

export default function App() {
  const [apiState, setApiState] = useState<ApiState>("checking");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [uploadError, setUploadError] = useState<string | null>(null);
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

  async function uploadDocument() {
    if (!selectedFile) return;

    setUploadState("uploading");
    setUploadError(null);
    setBundle(null);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch("/api/v1/documents/upload", {
        method: "POST",
        body: formData,
      });
      const payload = (await response.json()) as SourceBundle | { detail?: string };

      if (!response.ok) {
        const detail = "detail" in payload && payload.detail ? payload.detail : "Upload failed.";
        throw new Error(detail);
      }

      setBundle(payload as SourceBundle);
      setUploadState("success");
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Upload failed.");
      setUploadState("error");
    }
  }

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">LOCAL-FIRST · EVIDENCE-GROUNDED</p>
        <h1>VerityGraph AI</h1>
        <p className="lede">
          Turn documents and public web sources into connected intelligence where every
          relationship can be traced back to evidence.
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

      <section className="workspace" aria-labelledby="documents-heading">
        <div className="workspace-copy">
          <p className="section-label">01 · DOCUMENT INTELLIGENCE</p>
          <h2 id="documents-heading">Bring your own source</h2>
          <p>
            Upload a PDF, DOCX or TXT file. VerityGraph extracts traceable source spans before
            any NLP or graph analysis happens, so future claims can always point back to origin.
          </p>
          <ul className="trust-list">
            <li>Files stay inside your local deployment.</li>
            <li>10 MB safety limit in this first release.</li>
            <li>Page and paragraph provenance is retained when the format exposes it.</li>
          </ul>
        </div>

        <div className="upload-card">
          <label className="file-picker" htmlFor="document-upload">
            <span className="file-picker-title">Choose a source document</span>
            <span className="file-picker-help">PDF · DOCX · TXT</span>
            <input
              id="document-upload"
              data-testid="document-input"
              type="file"
              accept=".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(event) => {
                setSelectedFile(event.target.files?.[0] ?? null);
                setUploadState("idle");
                setUploadError(null);
                setBundle(null);
              }}
            />
          </label>

          <div className="upload-actions">
            <div>
              <strong>{selectedFile ? selectedFile.name : "No document selected"}</strong>
              {selectedFile && <span>{Math.max(1, Math.ceil(selectedFile.size / 1024))} KB</span>}
            </div>
            <button
              type="button"
              onClick={() => void uploadDocument()}
              disabled={!selectedFile || uploadState === "uploading" || apiState !== "healthy"}
            >
              {uploadState === "uploading" ? "Extracting evidence…" : "Analyse document"}
            </button>
          </div>

          <div className="upload-feedback" aria-live="polite" data-testid="upload-status">
            {uploadState === "idle" && "Select a supported document to begin."}
            {uploadState === "uploading" && "Parsing locally and building provenance spans…"}
            {uploadState === "success" && bundle && `Ready · ${bundle.spans.length} evidence spans extracted.`}
            {uploadState === "error" && uploadError}
          </div>
        </div>
      </section>

      {bundle && (
        <section className="source-preview" data-testid="source-preview" aria-labelledby="preview-heading">
          <div className="preview-header">
            <div>
              <p className="section-label">SOURCE PROVENANCE</p>
              <h2 id="preview-heading">{bundle.document.filename}</h2>
            </div>
            <div className="source-badges">
              <span>{bundle.document.source_format.toUpperCase()}</span>
              <span>{bundle.spans.length} spans</span>
              <span>{bundle.document.size_bytes.toLocaleString()} bytes</span>
            </div>
          </div>

          <div className="source-meta">
            <div><span>Source ID</span><code>{bundle.document.source_id}</code></div>
            <div><span>SHA-256</span><code>{bundle.document.content_hash.slice(0, 20)}…</code></div>
          </div>

          <div className="span-list">
            {bundle.spans.slice(0, 12).map((span) => (
              <article className="span-row" key={span.span_id}>
                <div>
                  <span className="span-location">{spanLocation(span)}</span>
                  <span className="span-offset">chars {span.char_start}–{span.char_end}</span>
                </div>
                <p>{span.text}</p>
              </article>
            ))}
          </div>

          {bundle.spans.length > 12 && (
            <p className="preview-note">Showing the first 12 of {bundle.spans.length} spans.</p>
          )}
        </section>
      )}

      <section className="next-grid" aria-label="Product roadmap entry points">
        <article>
          <span>02</span>
          <h3>Explore public knowledge</h3>
          <p>Wikipedia search, selected sections and permitted public URLs are next.</p>
        </article>
        <article>
          <span>03</span>
          <h3>Build the evidence graph</h3>
          <p>NER, relationship extraction and entity resolution will consume these same spans.</p>
        </article>
        <article>
          <span>04</span>
          <h3>Verify and improve</h3>
          <p>Claim inspection, response ratings, frozen-evidence revisions and version history.</p>
        </article>
      </section>
    </main>
  );
}
