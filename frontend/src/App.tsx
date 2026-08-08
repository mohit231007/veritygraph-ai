import { useEffect, useState } from "react";

type ApiState = "checking" | "healthy" | "unavailable";

type HealthResponse = {
  status: string;
  service: string;
  version: string;
};

export default function App() {
  const [apiState, setApiState] = useState<ApiState>("checking");
  const [health, setHealth] = useState<HealthResponse | null>(null);

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
          <p className="section-label" id="system-status-heading">Foundation status</p>
          <h2>Browser → API contract</h2>
        </div>
        <span className={`status status-${apiState}`} data-testid="api-status">
          {apiState === "checking" && "Checking API…"}
          {apiState === "healthy" && "API healthy"}
          {apiState === "unavailable" && "API unavailable"}
        </span>
        {health && <p className="version">{health.service} · v{health.version}</p>}
      </section>

      <section className="next-grid" aria-label="Planned product entry points">
        <article>
          <span>01</span>
          <h3>Analyse documents</h3>
          <p>PDF, DOCX and TXT with page- and paragraph-level provenance.</p>
        </article>
        <article>
          <span>02</span>
          <h3>Explore public knowledge</h3>
          <p>Wikipedia search, selected sections and permitted public URLs.</p>
        </article>
        <article>
          <span>03</span>
          <h3>Verify every insight</h3>
          <p>Graph edges, evidence spans, confidence explanations and version history.</p>
        </article>
      </section>
    </main>
  );
}
