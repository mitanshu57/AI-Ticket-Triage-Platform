"""Classification metrics for the eval pipeline (ADR-0010).

Pure functions over (gold, predicted) pairs — accuracy, per-label
precision/recall/F1, macro-F1, and a confusion matrix.
"""

from __future__ import annotations

from pydantic import BaseModel

Pair = tuple[str, str]  # (gold, predicted)


class LabelScore(BaseModel):
    precision: float
    recall: float
    f1: float
    support: int


class ClassificationReport(BaseModel):
    n: int
    accuracy: float
    macro_f1: float
    per_label: dict[str, LabelScore]
    confusion: dict[str, dict[str, int]]


def accuracy(pairs: list[Pair]) -> float:
    if not pairs:
        return 0.0
    correct = sum(1 for gold, pred in pairs if gold == pred)
    return correct / len(pairs)


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def label_scores(pairs: list[Pair]) -> dict[str, LabelScore]:
    labels = sorted({gold for gold, _ in pairs} | {pred for _, pred in pairs})
    scores: dict[str, LabelScore] = {}
    for label in labels:
        tp = sum(1 for g, p in pairs if g == label and p == label)
        fp = sum(1 for g, p in pairs if p == label and g != label)
        fn = sum(1 for g, p in pairs if g == label and p != label)
        support = sum(1 for g, _ in pairs if g == label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        scores[label] = LabelScore(
            precision=precision, recall=recall, f1=_f1(precision, recall), support=support
        )
    return scores


def confusion_matrix(pairs: list[Pair]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {}
    for gold, pred in pairs:
        matrix.setdefault(gold, {})
        matrix[gold][pred] = matrix[gold].get(pred, 0) + 1
    return matrix


def build_report(pairs: list[Pair]) -> ClassificationReport:
    per_label = label_scores(pairs)
    # Macro-F1 averages over labels that actually appear as gold (have support).
    gold_labels = [s for s in per_label.values() if s.support > 0]
    macro_f1 = sum(s.f1 for s in gold_labels) / len(gold_labels) if gold_labels else 0.0
    return ClassificationReport(
        n=len(pairs),
        accuracy=accuracy(pairs),
        macro_f1=macro_f1,
        per_label=per_label,
        confusion=confusion_matrix(pairs),
    )
