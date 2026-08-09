import { useState } from "react";

import type { SourceBundle } from "../types";

type UploadState = "idle" | "uploading" | "success" | "error";

type Props = {
  apiHealthy: boolean;
  onBundle: (bundle: SourceBundle) => void;
};

export default function DocumentWorkspace({ apiHealthy, onBundle }: Props) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [spanCount, setSpanCount] = useState(0);

  async function uploadDocument() {
    if (!selectedFile) return;

    setUploadState("uploading");
    setUploadError(null);
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

      const bundle = payload as SourceBundle;
      setSpanCount(bundle.spans.length);
      setUploadState("success");
      onBundle(bundle);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Upload failed.");
      setUploadState("error");
    }
  }

  return (
    <section className="workspace" aria-labelledby="documents-heading">
      <div className="workspace-copy">
        <p className="section-label">DOCUMENT INTELLIGENCE</p>
        <h2 id="documents-heading">Bring your own source</h2>
        <p>
          Upload a PDF, DOCX or TXT file. VerityGraph creates traceable evidence spans before
          any NLP or graph analysis runs.
        </p>
        <ul className="trust-list">
          <li>Files stay inside your local deployment.</li>
          <li>10 MB safety limit in this release.</li>
          <li>Page and paragraph provenance is retained when the source format exposes it.</li>
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
            disabled={!selectedFile || uploadState === "uploading" || !apiHealthy}
          >
            {uploadState === "uploading" ? "Extracting evidence…" : "Analyse document"}
          </button>
        </div>

        <div className="upload-feedback" aria-live="polite" data-testid="upload-status">
          {uploadState === "idle" && "Select a supported document to begin."}
          {uploadState === "uploading" && "Parsing locally and building provenance spans…"}
          {uploadState === "success" && `Ready · ${spanCount} evidence spans extracted.`}
          {uploadState === "error" && uploadError}
        </div>
      </div>
    </section>
  );
}
