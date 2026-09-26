"""
Runs a rubric over a dataset and a set of answers, and builds a summary.

The result is a plain dict, so it can go straight to JSON, SQLite,
the API, the dashboard, or the Markdown report without any conversion.
"""

import time
from collections import Counter, defaultdict

from dataset import Case
from rubric import CaseResult, Rubric


def summarize(results: list[CaseResult]) -> dict:
    total = len(results)
    passed = sum(r.passed for r in results)
    missing = sum(r.answer is None for r in results)

    # Mean per metric, counting only cases where the metric applied.
    metric_scores: dict[str, list[float]] = defaultdict(list)
    for r in results:
        for m in r.metrics:
            if m.score is not None:
                metric_scores[m.name].append(m.score)
    metric_means = {name: round(sum(v) / len(v), 4) for name, v in metric_scores.items()}

    by_tag: dict[str, dict] = defaultdict(lambda: {"total": 0, "passed": 0})
    for r in results:
        for tag in r.tags or ["untagged"]:
            by_tag[tag]["total"] += 1
            by_tag[tag]["passed"] += int(r.passed)
    for stats in by_tag.values():
        stats["pass_rate"] = round(stats["passed"] / stats["total"], 4)

    # Which metric caused failures most often. Helps decide what to fix first.
    fail_causes: Counter = Counter()
    for r in results:
        if r.answer is None:
            fail_causes["missing answer"] += 1
        for m in r.metrics:
            if m.below_minimum:
                fail_causes[m.name] += 1
        if any("pass mark" in reason for reason in r.reasons):
            fail_causes["low total score"] += 1

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "missing": missing,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "mean_score": round(sum(r.score for r in results) / total, 4) if total else 0.0,
        "metric_means": metric_means,
        "by_tag": dict(sorted(by_tag.items())),
        "fail_causes": dict(fail_causes.most_common()),
    }


def evaluate(
    cases: list[Case],
    answers: dict[str, str],
    rubric: Rubric,
    name: str = "",
    dataset_name: str = "",
    answers_name: str = "",
) -> dict:
    """Grade every case and return the full run as a dict."""
    started = time.perf_counter()

    results = []
    for case in cases:
        if case.id in answers:
            results.append(rubric.grade(case, answers[case.id]))
        else:
            results.append(rubric.missing_answer(case))

    warnings = []
    extra_ids = sorted(set(answers) - {c.id for c in cases})
    if extra_ids:
        shown = ", ".join(extra_ids[:5]) + (" ..." if len(extra_ids) > 5 else "")
        warnings.append(f"{len(extra_ids)} answer(s) have no matching case and were ignored: {shown}")

    return {
        "name": name or answers_name or "run",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": dataset_name,
        "answers": answers_name,
        "rubric": rubric.to_dict(),
        "summary": summarize(results),
        "cases": [r.to_dict() for r in results],
        "warnings": warnings,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
