"""Offline LLM evaluation runner (ADR-0010).

Runs the configured triage engine over a labeled dataset and reports
classification quality for category and priority. Deterministic with the stub
engine (so it runs in CI without a key); measures the real model when
ANTHROPIC_API_KEY is set.

Usage:
    python -m app.eval.run [path/to/dataset.json]
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from app.eval.metrics import ClassificationReport, build_report
from app.modules.triage.engine import TriageEngine, get_triage_engine, normalize_classification

DEFAULT_DATASET = Path(__file__).parent / "dataset.json"


def load_dataset(path: Path = DEFAULT_DATASET) -> list[dict]:
    return json.loads(path.read_text())


async def run_eval(
    engine: TriageEngine | None = None,
    dataset: list[dict] | None = None,
) -> dict[str, ClassificationReport]:
    """Classify every example and return per-field reports."""
    engine = engine or get_triage_engine()
    dataset = dataset if dataset is not None else load_dataset()

    category_pairs: list[tuple[str, str]] = []
    priority_pairs: list[tuple[str, str]] = []

    for ex in dataset:
        c = normalize_classification(await engine.classify(ex["subject"], ex["body"]))
        category_pairs.append((ex["category"], c.category))
        priority_pairs.append((ex["priority"], str(c.priority)))

    return {
        "category": build_report(category_pairs),
        "priority": build_report(priority_pairs),
    }


def format_report(name: str, report: ClassificationReport) -> str:
    lines = [
        f"== {name} ==",
        f"n={report.n}  accuracy={report.accuracy:.3f}  macro_f1={report.macro_f1:.3f}",
        f"{'label':<18}{'prec':>6}{'rec':>6}{'f1':>6}{'support':>9}",
    ]
    for label, s in sorted(report.per_label.items()):
        lines.append(
            f"{label:<18}{s.precision:>6.2f}{s.recall:>6.2f}{s.f1:>6.2f}{s.support:>9}"
        )
    return "\n".join(lines)


async def _main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATASET
    reports = await run_eval(dataset=load_dataset(path))
    for name, report in reports.items():
        print(format_report(name, report))
        print()


if __name__ == "__main__":
    asyncio.run(_main())
