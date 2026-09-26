"""
Metrics and the metric registry.

A metric is a function:

    def my_metric(answer: str, case: Case, params: dict) -> MetricResult

It returns a score from 0.0 to 1.0 and a short human-readable detail.
If a metric does not apply to a case (for example keyword_recall when
the case has no keywords), it returns score=None. The rubric then
leaves it out instead of giving a free 1.0 or an unfair 0.0.

Metrics register themselves with @register("name", "description").
The rubric picks metrics by name, so adding a metric never means
editing the evaluator. See plugin_numbers.py for an example.
"""

from dataclasses import dataclass, field
from typing import Callable

from dataset import Case
from lcs import lcs_indices
from text_utils import contains_phrase, normalize, tokenize


@dataclass
class MetricResult:
    score: float | None
    detail: str
    extra: dict = field(default_factory=dict)

    @property
    def applicable(self) -> bool:
        return self.score is not None


MetricFn = Callable[[str, Case, dict], MetricResult]


@dataclass
class MetricInfo:
    name: str
    fn: MetricFn
    description: str


METRICS: dict[str, MetricInfo] = {}


def register(name: str, description: str):
    """Decorator that adds a metric to the registry."""
    def decorator(fn: MetricFn) -> MetricFn:
        if name in METRICS:
            raise ValueError(f"Metric '{name}' is already registered")
        METRICS[name] = MetricInfo(name, fn, description)
        return fn
    return decorator


def get_metric(name: str) -> MetricInfo:
    if name not in METRICS:
        known = ", ".join(sorted(METRICS))
        raise KeyError(f"Unknown metric '{name}'. Known metrics: {known}")
    return METRICS[name]


def list_metrics() -> list[dict]:
    return [{"name": m.name, "description": m.description} for m in METRICS.values()]


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


# ---------------- built-in metrics ----------------

@register("exact_match", "1 if the answer equals the reference (or an alias) after normalizing, else 0.")
def exact_match(answer: str, case: Case, params: dict) -> MetricResult:
    target = normalize(answer)
    for option in [case.reference, *case.aliases]:
        if target == normalize(option):
            return MetricResult(1.0, "matches the reference exactly")
    return MetricResult(0.0, "does not match the reference exactly")


@register("keyword_recall", "Share of the case's required keywords that appear in the answer.")
def keyword_recall(answer: str, case: Case, params: dict) -> MetricResult:
    if not case.keywords:
        return MetricResult(None, "no keywords set for this case")

    answer_tokens = tokenize(answer)
    found = [k for k in case.keywords if contains_phrase(answer_tokens, k)]
    missing = [k for k in case.keywords if k not in found]

    detail = f"{len(found)}/{len(case.keywords)} keywords found"
    if missing:
        detail += f", missing: {', '.join(missing)}"
    return MetricResult(len(found) / len(case.keywords), detail, {"found": found, "missing": missing})


@register("rouge_l", "ROUGE-L F-score: longest common word subsequence between answer and reference.")
def rouge_l(answer: str, case: Case, params: dict) -> MetricResult:
    drop = bool(params.get("drop_stopwords", False))
    beta = float(params.get("beta", 1.0))

    answer_tokens = tokenize(answer, drop_stopwords=drop)
    reference_tokens = tokenize(case.reference, drop_stopwords=drop)
    if not answer_tokens or not reference_tokens:
        return MetricResult(0.0, "answer or reference is empty", {"answer_tokens": answer_tokens, "matched": []})

    matched, _ = lcs_indices(answer_tokens, reference_tokens)
    lcs = len(matched)
    precision = lcs / len(answer_tokens)
    recall = lcs / len(reference_tokens)

    if lcs == 0:
        f_score = 0.0
    else:
        f_score = (1 + beta ** 2) * precision * recall / (recall + beta ** 2 * precision)

    return MetricResult(
        round(f_score, 4),
        f"LCS {lcs} words, precision {precision:.2f}, recall {recall:.2f}",
        {"answer_tokens": answer_tokens, "matched": matched, "precision": precision, "recall": recall},
    )


@register("length_ratio", "1 if answer length is within [min_ratio, max_ratio] of the reference, lower outside.")
def length_ratio(answer: str, case: Case, params: dict) -> MetricResult:
    low = float(params.get("min_ratio", 0.5))
    high = float(params.get("max_ratio", 2.0))

    answer_len = len(tokenize(answer))
    reference_len = len(tokenize(case.reference))
    if reference_len == 0:
        return MetricResult(None, "reference is empty")

    ratio = answer_len / reference_len
    if ratio < low:
        score, verdict = ratio / low, "too short"
    elif ratio > high:
        score, verdict = high / ratio, "too long"
    else:
        score, verdict = 1.0, "good length"

    return MetricResult(round(clamp(score), 4), f"{answer_len} vs {reference_len} words (x{ratio:.2f}), {verdict}")


@register("no_forbidden", "0 if the answer contains any forbidden phrase (rubric-wide or per case), else 1.")
def no_forbidden(answer: str, case: Case, params: dict) -> MetricResult:
    phrases = list(params.get("phrases", [])) + case.forbidden
    if not phrases:
        return MetricResult(None, "no forbidden phrases configured")

    answer_tokens = tokenize(answer)
    hits = [p for p in phrases if contains_phrase(answer_tokens, p)]
    if hits:
        return MetricResult(0.0, f"contains: {', '.join(hits)}", {"hits": hits})
    return MetricResult(1.0, "no forbidden phrases")
