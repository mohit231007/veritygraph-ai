from pathlib import Path

from evaluation.benchmark import run_benchmark


ROOT = Path(__file__).resolve().parents[2]


def test_starter_relation_benchmark_runs_with_real_local_model() -> None:
    report = run_benchmark(
        ROOT / "evaluation" / "gold" / "basic_relations.json",
        "en_core_web_sm",
    )

    assert report["case_count"] == 4
    assert report["model"] == "en_core_web_sm"
    assert report["model_version"]
    assert report["pipeline_version"] == "spacy-baseline-v1"
    assert report["extractor_version"] == "dependency-relations-v1"
    assert 0.0 <= report["metrics"]["precision"] <= 1.0
    assert 0.0 <= report["metrics"]["recall"] <= 1.0
    assert 0.0 <= report["metrics"]["f1"] <= 1.0
    assert "production accuracy" in report["warning"]
