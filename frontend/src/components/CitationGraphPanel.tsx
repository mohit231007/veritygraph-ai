import { useEffect, useRef, useState } from "react";
import cytoscape, { type Core } from "cytoscape";

import "../citation-graph.css";
import type { WorkspaceDetail } from "../types";

type CitationMechanism = "url_reference" | "bibliographic_identifier";

type CitationNode = {
  source_id: string;
  label: string;
  source_type: "document" | "wikipedia" | "public_url";
  incoming_edge_count: number;
  outgoing_edge_count: number;
};

type CitationEdge = {
  edge_id: string;
  source_id: string;
  source_label: string;
  target_source_id: string;
  target_label: string;
  mechanisms: CitationMechanism[];
  url_reference_ids: string[];
  identifier_ids: string[];
  bibliographic_identities: string[];
  evidence_count: number;
  self_edge: boolean;
};

type CitationGraph = {
  workspace_id: string;
  graph_version: string;
  summary: {
    source_count: number;
    edge_count: number;
    sources_with_outgoing_count: number;
    sources_with_incoming_count: number;
    url_reference_evidence_count: number;
    identifier_reference_evidence_count: number;
    unresolved_url_reference_count: number;
    ambiguous_url_reference_count: number;
    unresolved_identifier_reference_count: number;
    ambiguous_identifier_reference_count: number;
    self_edge_count: number;
  };
  nodes: CitationNode[];
  edges: CitationEdge[];
  interpretation_note: string;
};

type Props = {
  apiHealthy: boolean;
  workspace: WorkspaceDetail | null;
};

function mechanismLabel(mechanisms: CitationMechanism[]) {
  if (mechanisms.length === 2) return "URL + bibliographic ID";
  return mechanisms[0] === "bibliographic_identifier" ? "Bibliographic ID" : "URL reference";
}

export default function CitationGraphPanel({ apiHealthy, workspace }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cytoscapeRef = useRef<Core | null>(null);
  const [graph, setGraph] = useState<CitationGraph | null>(null);
  const [message, setMessage] = useState("Add sources to project explicit citation topology.");

  useEffect(() => {
    if (!apiHealthy || !workspace) {
      setGraph(null);
      setMessage("Add sources to project explicit citation topology.");
      return;
    }

    const workspaceId = workspace.workspace_id;
    const controller = new AbortController();
    setMessage("Projecting uniquely resolved explicit references into source topology…");

    async function loadGraph() {
      try {
        const response = await fetch(`/api/v1/workspaces/${workspaceId}/citation-graph`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Could not build the explicit citation graph.");
        const payload = (await response.json()) as CitationGraph;
        setGraph(payload);
        setMessage(
          `Citation graph ready · ${payload.summary.source_count} sources · ${payload.summary.edge_count} directed edge${payload.summary.edge_count === 1 ? "" : "s"} · ${payload.summary.unresolved_url_reference_count + payload.summary.unresolved_identifier_reference_count} unresolved · ${payload.summary.ambiguous_url_reference_count + payload.summary.ambiguous_identifier_reference_count} ambiguous`,
        );
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setGraph(null);
        setMessage(error instanceof Error ? error.message : "Could not build citation graph.");
      }
    }

    void loadGraph();
    return () => controller.abort();
  }, [apiHealthy, workspace]);

  useEffect(() => {
    if (!containerRef.current || !graph) {
      cytoscapeRef.current?.destroy();
      cytoscapeRef.current = null;
      return;
    }

    cytoscapeRef.current?.destroy();
    const instance = cytoscape({
      container: containerRef.current,
      elements: [
        ...graph.nodes.map((node) => ({
          group: "nodes" as const,
          data: {
            id: node.source_id,
            label: node.label,
            incoming: node.incoming_edge_count,
            outgoing: node.outgoing_edge_count,
          },
        })),
        ...graph.edges.map((edge) => ({
          group: "edges" as const,
          data: {
            id: edge.edge_id,
            source: edge.source_id,
            target: edge.target_source_id,
            label: mechanismLabel(edge.mechanisms),
            evidenceCount: edge.evidence_count,
          },
        })),
      ],
      layout: { name: "cose", animate: false },
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": 11,
            "text-wrap": "wrap",
            "text-max-width": "100px",
            "text-valign": "bottom",
            "text-margin-y": 9,
            width: 38,
            height: 38,
            "background-color": "#8ea7d7",
            "border-width": 2,
            "border-color": "#dce6ff",
            color: "#f7f9ff",
          },
        },
        {
          selector: "edge",
          style: {
            label: "data(label)",
            "font-size": 9,
            width: "mapData(evidenceCount, 1, 8, 1.5, 5)",
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "line-color": "#77958f",
            "target-arrow-color": "#77958f",
            color: "#b8c9c3",
            "text-background-color": "#11182a",
            "text-background-opacity": 0.85,
            "text-background-padding": "3px",
          },
        },
      ],
    });
    cytoscapeRef.current = instance;

    return () => {
      instance.destroy();
      if (cytoscapeRef.current === instance) cytoscapeRef.current = null;
    };
  }, [graph]);

  return (
    <section className="citation-graph-panel" aria-labelledby="citation-graph-heading" data-testid="citation-graph-panel">
      <div className="citation-graph-heading">
        <div>
          <p className="section-label">EXPLICIT CITATION GRAPH</p>
          <h2 id="citation-graph-heading">Source-to-source reference topology</h2>
        </div>
        {graph && <span>{graph.graph_version}</span>}
      </div>

      <p className="citation-graph-status" aria-live="polite" data-testid="citation-graph-status">{message}</p>

      {graph && (
        <>
          <div className="citation-graph-metrics" data-testid="citation-graph-metrics">
            <article><span>Sources</span><strong>{graph.summary.source_count}</strong></article>
            <article data-testid="citation-edge-count"><span>Directed edges</span><strong>{graph.summary.edge_count}</strong></article>
            <article><span>URL evidence</span><strong>{graph.summary.url_reference_evidence_count}</strong></article>
            <article><span>Identifier evidence</span><strong>{graph.summary.identifier_reference_evidence_count}</strong></article>
            <article><span>Unresolved</span><strong>{graph.summary.unresolved_url_reference_count + graph.summary.unresolved_identifier_reference_count}</strong></article>
            <article><span>Ambiguous</span><strong>{graph.summary.ambiguous_url_reference_count + graph.summary.ambiguous_identifier_reference_count}</strong></article>
          </div>

          <aside className="citation-graph-guardrail" data-testid="citation-graph-guardrail">
            <strong>Edge = explicit uniquely resolved reference, not factual support or truth.</strong>
            <p>{graph.interpretation_note}</p>
          </aside>

          <div className="citation-graph-canvas" ref={containerRef} data-testid="citation-graph-canvas" />

          <div className="citation-edge-list" data-testid="citation-edge-list">
            {graph.edges.map((edge) => (
              <article key={edge.edge_id} data-testid="citation-edge-card">
                <div className="citation-edge-path">
                  <strong>{edge.source_label}</strong><span>→</span><strong>{edge.target_label}</strong>
                </div>
                <p>{mechanismLabel(edge.mechanisms)} · {edge.evidence_count} retained evidence item{edge.evidence_count === 1 ? "" : "s"}</p>
                {edge.url_reference_ids.length > 0 && <p>URL references · {edge.url_reference_ids.join(" · ")}</p>}
                {edge.bibliographic_identities.length > 0 && <p>Identifiers · {edge.bibliographic_identities.join(" · ")}</p>}
                {edge.self_edge && <footer>Explicit self-reference</footer>}
              </article>
            ))}
            {graph.edges.length === 0 && (
              <p className="citation-graph-empty">No uniquely resolved explicit source-to-source references are currently eligible for citation topology.</p>
            )}
          </div>
        </>
      )}
    </section>
  );
}
