"""Eval-pipeline tests — metric correctness and an end-to-end run over the
bundled dataset with the deterministic stub engine."""

from app.eval.metrics import accuracy, build_report, confusion_matrix, label_scores
from app.eval.run import load_dataset, run_eval
from app.modules.triage.engine import StubTriageEngine


def test_accuracy():
    assert accuracy([("a", "a"), ("a", "b"), ("b", "b")]) == 2 / 3
    assert accuracy([]) == 0.0


def test_label_scores_precision_recall_f1():
    # gold: a a b ; pred: a b b  -> label "a": tp=1, fp=0, fn=1
    pairs = [("a", "a"), ("a", "b"), ("b", "b")]
    scores = label_scores(pairs)
    a = scores["a"]
    assert a.precision == 1.0  # 1 / (1 + 0)
    assert a.recall == 0.5  # 1 / (1 + 1)
    assert abs(a.f1 - (2 * 1.0 * 0.5 / 1.5)) < 1e-9
    assert a.support == 2
    b = scores["b"]
    assert b.precision == 0.5  # 1 / (1 + 1)
    assert b.recall == 1.0


def test_confusion_matrix():
    cm = confusion_matrix([("a", "a"), ("a", "b"), ("b", "b")])
    assert cm["a"] == {"a": 1, "b": 1}
    assert cm["b"] == {"b": 1}


def test_build_report_perfect():
    pairs = [("a", "a"), ("b", "b"), ("a", "a")]
    report = build_report(pairs)
    assert report.accuracy == 1.0
    assert report.macro_f1 == 1.0
    assert report.n == 3


async def test_run_eval_over_dataset_meets_threshold():
    reports = await run_eval(engine=StubTriageEngine())
    cat = reports["category"]
    assert cat.n == len(load_dataset())
    # The stub is deterministic; it should classify the bundled set well.
    assert cat.accuracy >= 0.7
    assert "priority" in reports
    # Every gold category should be represented in the report.
    assert "billing" in cat.per_label
