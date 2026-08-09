from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.domain.source import SourceBundle, SourceDocument, SourceSpan, SourceType
from app.nlp.engine import SpacyNlpEngine
from evaluation.metrics import Triple, exact_triple_metrics

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = ROOT / "evaluation" / "gold" / "basic_relations.json"


def bundle_for_case(case_id: str, text: str) -> SourceBundle:
    source_id = f"eval_src_{case_id}"
    document = SourceDocument(
        source_id=source_id,
        source_type=SourceType.DOCUMENT,
        title=case_id,
        filename=f"{case_id}.txt",
        source_format="txt",
        mime_type="text/plain",
        content_hash="0" * 64,
        size_bytes=len(text.encode("utf-8")),
        metadata={"evaluation_case": case_id},
    )
    span = SourceSpan(
        span_id=f"eval_span_{case_id}",
        source_id=source_id,
        text=text,
        page_number=1,
        paragraph_number=1,
        char_start=0,
        char_end=len(text),
    )
    return SourceBundle(document=document, spans=[span])


def run_benchmark(gold_path: Path, model_name: str) -> dict:
    cases = json.loads(gold_path.read_text(encoding="utf-8"))
    engine = SpacyNlpEngine(model_name=model_name)

    predicted: set[Triple] = set()
    gold: set[Triple] = set()
    case_results: list[dict] = []

    for case in cases:
        bundle = bundle_for_case(case["case_id"], case["text"])
        entities, relations = engine.extract(
            run_id=f"eval_run_{case['case_id']}",
            bundles=[bundle],
        )
        names = {entity.entity_id: entity.canonical_name for entity in entities}
        predicted_case: set[Triple] = {
            (
                names[relation.subject_entity_id],
                relation.predicate,
                names[relation.object_entity_id],
            )
            for relation in relations
            if relation.subject_entity_id in names and relation.object_entity_id in names
        }
        gold_case: set[Triple] = {
            (relation["subject"], relation["predicate"], relation["object"])
            for relation in case["relations"]
        }
        predicted.update(predicted_case)
        gold.update(gold_case)
        case_metrics = exact_triple_metrics(predicted_case, gold_case)
        case_results.append(
            {
                "case_id": case["case_id"],
                "predicted": sorted(predicted_case),
                "gold": sorted(gold_case),
                "metrics": case_metrics.as_dict(),
            }
        )

    metrics = exact_triple_metrics(predicted, gold)
    return {
        "model": model_name,
        "model_version": engine.model_version,
        "pipeline_version": engine.PIPELINE_VERSION,
        "extractor_version": engine.EXTRACTOR_VERSION,
        "case_count": len(cases),
        "metrics": metrics.as_dict(),
        "cases": case_results,
        "warning": (
            "This starter benchmark is intentionally tiny and proves the evaluation path only. "
            "Do not present its score as production accuracy."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark VerityGraph relation extraction.")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--model", default="en_core_web_sm")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = run_benchmark(args.gold, args.model)
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
