"""
The rubric: which metrics to use, how much each one counts,
and what it takes to pass.

rubric.json
{
  "name": "Support bot rubric",
  "pass_threshold": 0.6,
  "plugins": ["plugin_numbers"],
  "metrics": {
    "rouge_l":        {"weight": 3},
    "keyword_recall": {"weight": 3, "min": 0.5},
    "numbers_match":  {"weight": 2, "min": 1.0}
  }
}

A case passes when:
  1. its weighted score is at least pass_threshold, and
  2. every metric with a "min" scores at least that min.

Rule 2 is a hard gate. A friendly, well written answer with the
wrong refund amount should fail even if the average looks fine.
"""

import importlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from dataset import Case
from metrics import MetricResult, get_metric

_MODULE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class RubricError(Exception):
    """Raised when rubric.json is not valid."""


@dataclass
class MetricRule:
    name: str
    weight: float
    minimum: float | None = None
    params: dict = field(default_factory=dict)


@dataclass
class MetricScore:
    name: str
    score: float | None
    weight: float
    detail: str
    minimum: float | None = None
    extra: dict = field(default_factory=dict)

    @property
    def below_minimum(self) -> bool:
        return self.minimum is not None and self.score is not None and self.score < self.minimum

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": self.score,
            "weight": self.weight,
            "detail": self.detail,
            "minimum": self.minimum,
            "below_minimum": self.below_minimum,
            "extra": self.extra,
        }


@dataclass
class CaseResult:
    case_id: str
    question: str
    reference: str
    answer: str | None
    score: float
    passed: bool
    metrics: list[MetricScore] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.case_id,
            "question": self.question,
            "reference": self.reference,
            "answer": self.answer,
            "score": self.score,
            "passed": self.passed,
            "metrics": [m.to_dict() for m in self.metrics],
            "reasons": self.reasons,
            "tags": self.tags,
        }


def load_plugins(modules: list[str]) -> None:
    """Import plugin modules so their @register calls run."""
    for module in modules:
        if not isinstance(module, str) or not _MODULE_NAME_RE.match(module):
            raise RubricError(f"Plugin name '{module}' must be a plain module name, like 'plugin_numbers'")
        try:
            importlib.import_module(module)
        except ImportError as exc:
            raise RubricError(f"Could not import plugin '{module}': {exc}") from exc


def _number(value, label: str, low: float | None = None, high: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RubricError(f"{label} must be a number")
    if (low is not None and value < low) or (high is not None and value > high):
        raise RubricError(f"{label} must be between {low} and {high}")
    return float(value)


class Rubric:
    def __init__(self, name: str, pass_threshold: float, rules: list[MetricRule], plugins: list[str] | None = None):
        self.name = name
        self.pass_threshold = pass_threshold
        self.rules = rules
        self.plugins = plugins or []

    # ----- loading -----

    @classmethod
    def from_dict(cls, data: dict) -> "Rubric":
        if not isinstance(data, dict):
            raise RubricError("Rubric must be a JSON object")

        plugins = data.get("plugins", [])
        if not isinstance(plugins, list):
            raise RubricError("'plugins' must be a list of module names")
        load_plugins(plugins)

        threshold = _number(data.get("pass_threshold", 0.6), "pass_threshold", 0, 1)

        metrics = data.get("metrics")
        if not isinstance(metrics, dict) or not metrics:
            raise RubricError("'metrics' must be a non-empty object")

        rules = []
        for name, settings in metrics.items():
            try:
                get_metric(name)
            except KeyError as exc:
                raise RubricError(str(exc)) from exc
            if not isinstance(settings, dict):
                raise RubricError(f"Settings for '{name}' must be an object")

            weight = _number(settings.get("weight", 1), f"{name}.weight", 0, None)
            minimum = settings.get("min")
            if minimum is not None:
                minimum = _number(minimum, f"{name}.min", 0, 1)
            params = settings.get("params", {})
            if not isinstance(params, dict):
                raise RubricError(f"{name}.params must be an object")
            rules.append(MetricRule(name, weight, minimum, params))

        if sum(r.weight for r in rules) <= 0:
            raise RubricError("At least one metric needs a weight above 0")

        return cls(str(data.get("name", "Unnamed rubric")), threshold, rules, plugins)

    @classmethod
    def load(cls, path: Path | str) -> "Rubric":
        path = Path(path)
        if not path.exists():
            raise RubricError(f"Rubric file not found: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RubricError(f"{path.name}: not valid JSON ({exc.msg}, line {exc.lineno})") from exc
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "pass_threshold": self.pass_threshold,
            "plugins": self.plugins,
            "metrics": {
                r.name: {"weight": r.weight, "min": r.minimum, "params": r.params} for r in self.rules
            },
        }

    # ----- grading -----

    def _run_metric(self, rule: MetricRule, answer: str, case: Case) -> MetricResult:
        try:
            return get_metric(rule.name).fn(answer, case, rule.params)
        except Exception as exc:  # a broken plugin should fail one case, not the whole run
            return MetricResult(0.0, f"metric error: {exc}")

    def grade(self, case: Case, answer: str) -> CaseResult:
        scores: list[MetricScore] = []
        for rule in self.rules:
            result = self._run_metric(rule, answer, case)
            scores.append(MetricScore(rule.name, result.score, rule.weight, result.detail, rule.minimum, result.extra))

        # Weighted average over metrics that apply to this case only.
        applicable = [s for s in scores if s.score is not None and s.weight > 0]
        total_weight = sum(s.weight for s in applicable)
        score = sum(s.score * s.weight for s in applicable) / total_weight if total_weight else 0.0
        score = round(score, 4)

        reasons = []
        if not applicable:
            reasons.append("no metric applies to this case")
        elif score < self.pass_threshold:
            reasons.append(f"score {score:.2f} is below the pass mark {self.pass_threshold:.2f}")
        for s in scores:
            if s.below_minimum:
                reasons.append(f"{s.name} {s.score:.2f} is below its minimum {s.minimum:.2f}")

        return CaseResult(
            case_id=case.id,
            question=case.question,
            reference=case.reference,
            answer=answer,
            score=score,
            passed=not reasons,
            metrics=scores,
            reasons=reasons,
            tags=case.tags,
        )

    def missing_answer(self, case: Case) -> CaseResult:
        return CaseResult(case.id, case.question, case.reference, None, 0.0, False,
                          reasons=["no answer for this case"], tags=case.tags)
