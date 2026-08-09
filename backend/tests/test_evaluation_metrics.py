from evaluation.metrics import exact_triple_metrics


def test_exact_triple_metrics_normalize_case_and_whitespace() -> None:
    predicted = {
        ("Microsoft", "acquire", "GitHub"),
        ("Microsoft", "invest in", "OpenAI"),
    }
    gold = {
        (" microsoft ", "ACQUIRE", "github"),
        ("Microsoft", "partner with", "OpenAI"),
    }

    metrics = exact_triple_metrics(predicted, gold)

    assert metrics.true_positives == 1
    assert metrics.false_positives == 1
    assert metrics.false_negatives == 1
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.f1 == 0.5
