"""
Example plugin metric.

This file shows how to add a metric without touching the core code.
List it under "plugins" in rubric.json and it gets imported, which
runs @register and adds the metric to the registry.

numbers_match: every number in the reference must appear in the answer.
For a support bot, "refund in 5 days" vs "refund in 7 days" reads almost
the same to ROUGE-L, but it is a wrong answer. This metric catches it.
"""

import re

from dataset import Case
from metrics import MetricResult, register

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def extract_numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUMBER_RE.findall(text)}


@register("numbers_match", "Every number in the reference must also appear in the answer.")
def numbers_match(answer: str, case: Case, params: dict) -> MetricResult:
    expected = extract_numbers(case.reference)
    if not expected:
        return MetricResult(None, "reference has no numbers")

    found = extract_numbers(answer)
    missing = sorted(expected - found)
    score = (len(expected) - len(missing)) / len(expected)

    if missing:
        return MetricResult(score, f"missing numbers: {', '.join(missing)}", {"missing": missing})
    return MetricResult(1.0, f"all {len(expected)} numbers present")
