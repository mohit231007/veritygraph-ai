import { useEffect, useMemo, useRef, useState } from "react";
import cytoscape, { type Core } from "cytoscape";

import "../graph.css";
import type {
  EvidenceGraph,
  GraphEdge,
  GraphNode,
  GraphPath,
  WorkspaceAnalysis,
  WorkspaceDetail,
} from "../types";

type LayoutName = "cose" | "circle" | "breadthfirst";

type Props = {
  apiHealthy: boolean;
  workspace: WorkspaceDetail | null;
  analysis: WorkspaceAnalysis | null;
};

function sourceLabel(workspace: WorkspaceDetail | null, sourceId: string) {
  const source = workspace?.sources.find((item) => item.source_id === sourceId);
  return source ? source.filename ?? source.title : sourceId;
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function edgeLabel(edge: Pick<GraphEdge, "predicate" | "polarity">) {
  if (edge.polarity === "negated") return `NOT ${edge.predicate}`;
  if (edge.polarity === "unknown") return `? ${edge.predicate}`;
  return edge.predicate;
}

export default function GraphPanel({ apiHealthy, workspace, analysis }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cytoscapeRef = useRef<Core | null>(null);
  const [graph, setGraph] = useState<EvidenceGraph | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [layout, setLayout] = useState<LayoutName>("cose");
  const [statusMessage, setStatusMessage] = useState("Run an analysis to unlock the evidence graph.");
  const [pathFrom, setPathFrom] = useState("");
  const [pathTo, setPathTo] = useState("");
  const [path, setPath] = useState<GraphPath | null>(null);
  const [pathMessage, setPathMessage] = useState("Choose two entities to inspect their connection.");

  const nodeById = useMemo(
    () => new Map(graph?.nodes.map((node) => [node.entity_id, node]) ?? []),
    [graph],
  );

  useEffect(() => {
    const runId = analysis?.run.run_id;
    if (!apiHealthy || !workspace || !runId) {
      setGraph(null);
      setSelectedNode(null);
      setSelectedEdge(null);
      setPath(null);
      setPathFrom("");
      setPathTo("");
      setStatusMessage("Run an analysis to unlock the evidence graph.");
      return;
    }

    const controller = new AbortController();
    setStatusMessage("Projecting the immutable analysis run into an evidence graph…");

    async function loadGraph() {
      try {
        const response = await fetch(`/api/v1/analyses/${runId}/graph`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Could not build the evidence graph.");
        const payload = (await response.json()) as EvidenceGraph;
        setGraph(payload);
        setPath(null);
        setPathFrom(payload.nodes[0]?.entity_id ?? "");
        setPathTo(payload.nodes[1]?.entity_id ?? payload.nodes[0]?.entity_id ?? "");
        setStatusMessage(
          `Graph ready · ${payload.summary.node_count} entities · ${payload.summary.edge_count} evidence assertions`,
        );
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setGraph(null);
        setStatusMessage(error instanceof Error ? error.message : "Could not build graph.");
      }
    }

    void loadGraph();
    return () => controller.abort();
  }, [analysis?.run.run_id, apiHealthy, workspace]);

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
            id: node.entity_id,
            entityId: node.entity_id,
            label: node.label,
            entityType: node.entity_type,
            pagerank: node.pagerank,
            community: node.community,
          },
        })),
        ...graph.edges.map((edge) => ({
          group: "edges" as const,
          data: {
            id: edge.relation_id,
            relationId: edge.relation_id,
            source: edge.source_entity_id,
            target: edge.target_entity_id,
            label: edgeLabel(edge),
            polarity: edge.polarity,
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
            "text-max-width": "90px",
            "text-valign": "bottom",
            "text-margin-y": 9,
            width: "mapData(pagerank, 0, 1, 28, 72)",
            height: "mapData(pagerank, 0, 1, 28, 72)",
            "background-color": "#84a7ff",
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
            "line-color": "#66738e",
            "target-arrow-color": "#66738e",
            color: "#b8c4de",
            "text-background-color": "#11182a",
            "text-background-opacity": 0.85,
            "text-background-padding": "3px",
          },
        },
        {
          selector: 'edge[polarity = "negated"]',
          style: {
            "line-style": "dashed",
            "line-color": "#b27a84",
            "target-arrow-color": "#b27a84",
            color: "#e2a5ae",
          },
        },
        {
          selector: ":selected",
          style: {
            "border-color": "#ffffff",
            "border-width": 4,
            "line-color": "#d9e4ff",
            "target-arrow-color": "#d9e4ff",
          },
        },
        {
          selector: ".path-highlight",
          style: {
            "background-color": "#d7ddff",
            "line-color": "#d7ddff",
            "target-arrow-color": "#d7ddff",
            "border-color": "#ffffff",
          },
        },
      ],
    });

    instance.on("tap", "node", (event) => {
      const entityId = event.target.data("entityId") as string;
      setSelectedEdge(null);
      setSelectedNode(graph.nodes.find((node) => node.entity_id === entityId) ?? null);
    });
    instance.on("tap", "edge", (event) => {
      const relationId = event.target.data("relationId") as string;
      setSelectedNode(null);
      setSelectedEdge(graph.edges.find((edge) => edge.relation_id === relationId) ?? null);
    });
    cytoscapeRef.current = instance;

    return () => {
      instance.destroy();
      if (cytoscapeRef.current === instance) cytoscapeRef.current = null;
    };
  }, [graph]);

  function changeLayout(nextLayout: LayoutName) {
    setLayout(nextLayout);
    const instance = cytoscapeRef.current;
    if (!instance) return;
    if (nextLayout === "circle") {
      instance.layout({ name: "circle", animate: false }).run();
    } else if (nextLayout === "breadthfirst") {
      instance.layout({ name: "breadthfirst", directed: true, animate: false }).run();
    } else {
      instance.layout({ name: "cose", animate: false }).run();
    }
  }

  function selectEdge(edge: GraphEdge) {
    setSelectedNode(null);
    setSelectedEdge(edge);
    const instance = cytoscapeRef.current;
    instance?.elements().unselect();
    instance?.getElementById(edge.relation_id).select();
  }

  function selectNode(node: GraphNode) {
    setSelectedEdge(null);
    setSelectedNode(node);
    const instance = cytoscapeRef.current;
    instance?.elements().unselect();
    const element = instance?.getElementById(node.entity_id);
    if (element && element.length > 0) {
      element.select();
      element.connectedEdges().connectedNodes().select();
    }
  }

  async function findPath() {
    if (!analysis || !pathFrom || !pathTo) return;
    setPathMessage("Computing the fewest-hop positive evidence connection…");
    const params = new URLSearchParams({
      source_entity_id: pathFrom,
      target_entity_id: pathTo,
    });
    try {
      const response = await fetch(
        `/api/v1/analyses/${analysis.run.run_id}/graph/path?${params.toString()}`,
      );
      const payload = (await response.json()) as GraphPath | { detail?: string };
      if (!response.ok) {
        throw new Error(
          "detail" in payload ? payload.detail ?? "No connection found." : "No connection found.",
        );
      }
      const resolved = payload as GraphPath;
      setPath(resolved);
      setPathMessage(
        `${resolved.hop_count} hop${resolved.hop_count === 1 ? "" : "s"} in the undirected non-negated evidence graph.`,
      );

      const instance = cytoscapeRef.current;
      instance?.elements().removeClass("path-highlight");
      resolved.entity_ids.forEach((entityId) => {
        instance?.getElementById(entityId).addClass("path-highlight");
      });
      resolved.steps.flatMap((step) => step.relation_ids).forEach((relationId) => {
        instance?.getElementById(relationId).addClass("path-highlight");
      });
    } catch (error) {
      setPath(null);
      setPathMessage(error instanceof Error ? error.message : "No connection found.");
    }
  }

  return (
    <section className="graph-panel" aria-labelledby="graph-heading" data-testid="graph-panel">
      <div className="graph-heading">
        <div>
          <p className="section-label">EVIDENCE GRAPH</p>
          <h2 id="graph-heading">Connected intelligence with inspectable lineage</h2>
        </div>
        <label>
          Layout
          <select
            value={layout}
            disabled={!graph}
            data-testid="graph-layout-select"
            onChange={(event) => changeLayout(event.target.value as LayoutName)}
          >
            <option value="cose">Force-directed</option>
            <option value="circle">Circle</option>
            <option value="breadthfirst">Breadth-first</option>
          </select>
        </label>
      </div>

      <p className="graph-status" aria-live="polite" data-testid="graph-status">
        {statusMessage}
      </p>

      {graph && (
        <>
          <div className="graph-metrics" data-testid="graph-metrics">
            <article><span>Entities</span><strong>{graph.summary.node_count}</strong></article>
            <article><span>Assertions</span><strong>{graph.summary.edge_count}</strong></article>
            <article><span>Positive density</span><strong>{percent(graph.summary.density)}</strong></article>
            <article><span>Components</span><strong>{graph.summary.weak_component_count}</strong></article>
            <article><span>Communities</span><strong>{graph.summary.community_count}</strong></article>
          </div>

          <div className="graph-workbench">
            <div className="graph-canvas-wrap">
              <div ref={containerRef} className="graph-canvas" data-testid="graph-canvas" />
              <p className="graph-legend">
                Node analytics use non-negated evidence only · dashed NOT edges remain inspectable but never create positive paths.
              </p>
            </div>

            <aside className="graph-inspector" data-testid="graph-inspector">
              {!selectedNode && !selectedEdge && (
                <div className="inspector-empty">
                  <strong>Inspect the graph</strong>
                  <p>Select an entity or assertion on the canvas or from the evidence lists below.</p>
                </div>
              )}

              {selectedNode && (
                <div data-testid="graph-node-detail">
                  <p className="inspector-kicker">ENTITY</p>
                  <h3>{selectedNode.label}</h3>
                  <p>{selectedNode.entity_type} · community {selectedNode.community + 1}</p>
                  <dl>
                    <div><dt>Mentions</dt><dd>{selectedNode.mention_count}</dd></div>
                    <div><dt>Sources</dt><dd>{selectedNode.source_count}</dd></div>
                    <div><dt>In / out degree</dt><dd>{selectedNode.in_degree} / {selectedNode.out_degree}</dd></div>
                    <div><dt>PageRank</dt><dd>{selectedNode.pagerank.toFixed(4)}</dd></div>
                    <div><dt>Betweenness</dt><dd>{selectedNode.betweenness.toFixed(4)}</dd></div>
                  </dl>
                </div>
              )}

              {selectedEdge && (
                <div data-testid="graph-edge-detail">
                  <p className="inspector-kicker">ASSERTION + EVIDENCE</p>
                  <h3>
                    {nodeById.get(selectedEdge.source_entity_id)?.label ?? selectedEdge.source_entity_id}
                    <span> {edgeLabel(selectedEdge)} </span>
                    {nodeById.get(selectedEdge.target_entity_id)?.label ?? selectedEdge.target_entity_id}
                  </h3>
                  <p>
                    {selectedEdge.polarity.toUpperCase()} · {selectedEdge.polarity_method.replaceAll("_", " ")}
                  </p>
                  <p>
                    {selectedEdge.evidence_count} evidence record{selectedEdge.evidence_count === 1 ? "" : "s"}
                    {" · "}{selectedEdge.source_count} source{selectedEdge.source_count === 1 ? "" : "s"}
                  </p>
                  <p>
                    Rule score {Math.round(selectedEdge.extraction_score * 100)} · {selectedEdge.extraction_method.replaceAll("_", " ")}
                  </p>
                  <div className="graph-evidence-list">
                    {selectedEdge.evidence.map((evidence) => (
                      <blockquote key={evidence.evidence_id}>
                        <p>“{evidence.text}”</p>
                        <footer>{sourceLabel(workspace, evidence.source_id)} · {evidence.span_id}</footer>
                      </blockquote>
                    ))}
                  </div>
                </div>
              )}
            </aside>
          </div>

          <div className="graph-lists">
            <section>
              <div className="graph-subheading">
                <h3>Central entities</h3>
                <span>Ranked on the non-negated structural projection</span>
              </div>
              <div className="graph-node-list" data-testid="graph-node-list">
                {graph.nodes.slice(0, 12).map((node, index) => (
                  <button type="button" key={node.entity_id} onClick={() => selectNode(node)}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{node.label}</strong>
                    <small>PR {node.pagerank.toFixed(3)} · B {node.betweenness.toFixed(3)}</small>
                  </button>
                ))}
              </div>
            </section>

            <section>
              <div className="graph-subheading">
                <h3>Evidence assertions</h3>
                <span>Every edge keeps polarity and source sentence lineage</span>
              </div>
              <div className="graph-edge-list" data-testid="graph-edge-list">
                {graph.edges.slice(0, 20).map((edge) => (
                  <button type="button" key={edge.relation_id} onClick={() => selectEdge(edge)}>
                    <strong>{nodeById.get(edge.source_entity_id)?.label ?? edge.source_entity_id}</strong>
                    <span>{edgeLabel(edge)}</span>
                    <strong>{nodeById.get(edge.target_entity_id)?.label ?? edge.target_entity_id}</strong>
                    <small>
                      {edge.polarity.toUpperCase()} · {edge.evidence_count} evidence · {edge.source_count} source{edge.source_count === 1 ? "" : "s"}
                    </small>
                  </button>
                ))}
              </div>
            </section>
          </div>

          <section className="path-finder" aria-labelledby="path-heading">
            <div className="graph-subheading">
              <h3 id="path-heading">Connection path</h3>
              <span>Fewest hops in the undirected non-negated evidence projection</span>
            </div>
            <div className="path-controls">
              <select
                data-testid="path-from"
                value={pathFrom}
                onChange={(event) => setPathFrom(event.target.value)}
              >
                {graph.nodes.map((node) => (
                  <option key={node.entity_id} value={node.entity_id}>{node.label}</option>
                ))}
              </select>
              <span>→</span>
              <select
                data-testid="path-to"
                value={pathTo}
                onChange={(event) => setPathTo(event.target.value)}
              >
                {graph.nodes.map((node) => (
                  <option key={node.entity_id} value={node.entity_id}>{node.label}</option>
                ))}
              </select>
              <button type="button" data-testid="find-path-button" onClick={() => void findPath()}>
                Find connection
              </button>
            </div>
            <p className="path-message" data-testid="path-message">{pathMessage}</p>
            {path && (
              <div className="path-result" data-testid="path-result">
                {path.entity_ids.map((entityId, index) => (
                  <span key={`${entityId}-${index}`}>
                    {nodeById.get(entityId)?.label ?? entityId}
                    {index < path.entity_ids.length - 1 && " → "}
                  </span>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </section>
  );
}
