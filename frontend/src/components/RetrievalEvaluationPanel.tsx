import { FormEvent, useEffect, useState } from "react";

import "../retrieval-evaluation.css";
import type { WorkspaceDetail } from "../types";

type EvaluationCaseInput = {
  case_id: string;
  query: string;
  relevant_span_ids: string[];
};

type AggregateMetric = {
  k: number;
  mean_recall: number;
  mean_precision: number;
  hit_rate: number;
};

type CaseMetric = {
  k: number;
  recall: number;
  precision: number;
  hit: boolean;
};

type EvaluationCaseResult = {
  case_id: string;
  query: string;
  relevant_span_ids: string[];
  retrieved_span_ids: string[];
  first_relevant_rank: number | null;
  reciprocal_rank: number;
  metrics_at_k: CaseMetric[];
};

type RetrievalEvaluation = {
  workspace_id: string;
  evaluation_version: string;
  retrieval_version: string;
  summary: {
    workspace_source_count: number;
    indexed_span_count: number;
    case_count: number;
    unique_relevant_span_count: number;
    mean_reciprocal_rank: number;
    metrics_at_k: AggregateMetric[];
  };
  cases: EvaluationCaseResult[];
  interpretation_note: string;
};

type Props = {
  apiHealthy: boolean;
  workspace: WorkspaceDetail | null;
};

const EXAMPLE_CASES = `[
  {
    "case_id": "case-1",
    "query": "accelerated networking evidence",
    "relevant_span_ids": ["span_..."]
  }
]`;

function parseKValues(value: string) {
  const parsed = value
    .split(",")
    .map((item) => Number.parseInt(item.trim(), 10))
    .filter((item) => Number.isInteger(item));
  return [...new Set(parsed)].sort((left, right) => left - right);
}

export default function RetrievalEvaluationPanel({ apiHealthy, workspace }: Props) {
  const [casesText, setCasesText] = useState(EXAMPLE_CASES);
  const [kText, setKText] = useState("1,3,5");
  const [evaluation, setEvaluation] = useState<RetrievalEvaluation | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(
    "Paste explicit relevant-span labels to benchmark the production ranker.",
  );

  useEffect(() => {
    setEvaluation(null);
    setMessage("Paste explicit relevant-span labels to benchmark the production ranker.");
  }, [workspace?.workspace_id]);

  async function runEvaluation(event: FormEvent) {
    event.preventDefault();
    if (!apiHealthy || !workspace) return;

    let cases: EvaluationCaseInput[];
    try {
      const parsed = JSON.parse(casesText) as unknown;
      if (!Array.isArray(parsed)) throw new Error("Cases must be a JSON array.");
      cases = parsed as EvaluationCaseInput[];
    } catch (error) {
      setEvaluation(null);
      setMessage(error instanceof Error ? error.message : "Cases must be valid JSON.");
      return;
    }

    const kValues = parseKValues(kText);
    if (kValues.length === 0) {
      setEvaluation(null);
      setMessage("Enter at least one integer K value between 1 and 25.");
      return;
    }

    setLoading(true);
    setMessage("Evaluating labelled retrieval cases…");
    try {
      const response = await fetch(
        `/api/v1/workspaces/${workspace.workspace_id}/retrieval/evaluate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cases, k_values: kValues }),
        },
      );
      const payload = (await response.json()) as RetrievalEvaluation | { detail?: string };
      if (!response.ok) {
        const detail = "detail" in payload && payload.detail ? payload.detail : "Evaluation failed.";
        throw new Error(detail);
      }
      const result = payload as RetrievalEvaluation;
      setEvaluation(result);
      setMessage(
        `Evaluation ready · ${result.summary.case_count} case${result.summary.case_count === 1 ? "" : "s"} · MRR ${result.summary.mean_reciprocal_rank.toFixed(3)}`,
      );
    } catch (error) {
      setEvaluation(null);
      setMessage(error instanceof Error ? error.message : "Evaluation failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section
      className="retrieval-evaluation-panel"
      aria-labelledby="retrieval-evaluation-heading"
      data-testid="retrieval-evaluation-panel"
    >
      <div className="retrieval-evaluation-heading">
        <div>
          <p className="section-label">RETRIEVAL EVALUATION LAB</p>
          <h2 id="retrieval-evaluation-heading">Measure the baseline before replacing it</h2>
        </div>
        {evaluation && <span>{evaluation.evaluation_version}</span>}
      </div>

      <form className="retrieval-evaluation-form" onSubmit={runEvaluation}>
        <label htmlFor="retrieval-evaluation-cases">Labelled cases JSON</label>
        <textarea
          id="retrieval-evaluation-cases"
          data-testid="retrieval-evaluation-cases-input"
          value={casesText}
          onChange={(event) => setCasesText(event.target.value)}
          rows={8}
          disabled={!apiHealthy || !workspace || loading}
        />
        <div className="retrieval-evaluation-actions">
          <label htmlFor="retrieval-evaluation-k">
            K values
            <input
              id="retrieval-evaluation-k"
              data-testid="retrieval-evaluation-k-input"
              value={kText}
              onChange={(event) => setKText(event.target.value)}
              disabled={!apiHealthy || !workspace || loading}
            />
          </label>
          <button
            type="submit"
            data-testid="retrieval-evaluation-button"
            disabled={!apiHealthy || !workspace || loading}
          >
            {loading ? "Evaluating…" : "Evaluate retrieval"}
          </button>
        </div>
      </form>

      <p
        className="retrieval-evaluation-status"
        aria-live="polite"
        data-testid="retrieval-evaluation-status"
      >
        {message}
      </p>

      {evaluation && (
        <>
          <div className="retrieval-evaluation-summary">
            <article><span>Cases</span><strong>{evaluation.summary.case_count}</strong></article>
            <article><span>Indexed spans</span><strong>{evaluation.summary.indexed_span_count}</strong></article>
            <article><span>Relevant spans</span><strong>{evaluation.summary.unique_relevant_span_count}</strong></article>
            <article data-testid="retrieval-mrr"><span>MRR</span><strong>{evaluation.summary.mean_reciprocal_rank.toFixed(3)}</strong></article>
          </div>

          <aside className="retrieval-evaluation-guardrail" data-testid="retrieval-evaluation-guardrail">
            <strong>Retrieval metric ≠ factual accuracy, answer quality, authority, or truth.</strong>
            <p>{evaluation.interpretation_note}</p>
          </aside>

          <div className="retrieval-evaluation-metrics" data-testid="retrieval-evaluation-metrics">
            {evaluation.summary.metrics_at_k.map((metric) => (
              <article key={metric.k} data-testid="retrieval-evaluation-metric-card">
                <strong>K = {metric.k}</strong>
                <p>Recall · {metric.mean_recall.toFixed(3)}</p>
                <p>Precision · {metric.mean_precision.toFixed(3)}</p>
                <p>Hit rate · {metric.hit_rate.toFixed(3)}</p>
              </article>
            ))}
          </div>

          <div className="retrieval-evaluation-cases" data-testid="retrieval-evaluation-case-list">
            {evaluation.cases.map((item) => (
              <article key={item.case_id} data-testid="retrieval-evaluation-case-card">
                <header>
                  <strong>{item.case_id}</strong>
                  <span>RR {item.reciprocal_rank.toFixed(3)}</span>
                </header>
                <p>{item.query}</p>
                <p>First relevant rank · {item.first_relevant_rank ?? "not retrieved"}</p>
                <footer>Relevant · {item.relevant_span_ids.join(" · ")}</footer>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
