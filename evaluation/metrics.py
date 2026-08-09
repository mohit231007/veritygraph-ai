from __future__ import annotations

from dataclasses import dataclass

Triple = tuple[str, str, str]


@dataclass(slots=True, frozen=True)
class ExactMatchMetrics:
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float

    def as_dict(self) -> dict[str, int | float]:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


def normalize_triple(triple: Triple) -> Triple:
    return tuple(" ".join(value.casefold().split()) for value in triple)  # type: ignore[return-value]


def exact_triple_metrics(predicted: set[Triple], gold: set[Triple]) -> ExactMatchMetrics:
    """Calculate exact normalized triple precision/recall/F1 without score inflation."""

    predicted_normalized = {normalize_triple(triple) for triple in predicted}
    gold_normalized = {normalize_triple(triple) for triple in gold}

    true_positives = len(predicted_normalized & gold_normalized)
    false_positives = len(predicted_normalized - gold_normalized)
    false_negatives = len(gold_normalized - predicted_normalized)

    precision = (
        true_positives / (true_positives + false_positives)
        if true_positives + false_positives
        else 0.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if true_positives + false_negatives
        else 0.0
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return ExactMatchMetrics(
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1=f1,
    )
