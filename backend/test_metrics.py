import pytest

import metrics
import plugin_numbers  # noqa: F401  registers numbers_match
from dataset import Case


def case(reference="Refunds take 5 business days.", **kwargs):
    return Case(id="t", question="q", reference=reference, **kwargs)


def run(name, answer, c, params=None):
    return metrics.get_metric(name).fn(answer, c, params or {})


# ---------- exact_match ----------

def test_exact_match_ignores_case_and_punctuation():
    assert run("exact_match", "refunds TAKE 5 business days", case()).score == 1.0


def test_exact_match_accepts_aliases():
    c = case(reference="Lahore", aliases=["Lahore, Pakistan"])
    assert run("exact_match", "lahore pakistan", c).score == 1.0
    assert run("exact_match", "Karachi", c).score == 0.0


# ---------- keyword_recall ----------

def test_keyword_recall_partial():
    result = run("keyword_recall", "You get a refund soon.", case(keywords=["refund", "5 business days"]))
    assert result.score == 0.5
    assert result.extra["missing"] == ["5 business days"]


def test_keyword_recall_not_applicable_without_keywords():
    assert run("keyword_recall", "anything", case()).score is None


# ---------- rouge_l ----------

def test_rouge_l_identical_is_one():
    assert run("rouge_l", "Refunds take 5 business days.", case()).score == 1.0


def test_rouge_l_no_overlap_is_zero():
    assert run("rouge_l", "Hello there", case()).score == 0.0


def test_rouge_l_known_value():
    # answer 4 words, reference 5 words, LCS 4 -> P=1.0, R=0.8, F1=0.8889
    result = run("rouge_l", "refunds take business days", case())
    assert result.score == pytest.approx(0.8889, abs=1e-4)
    assert result.extra["matched"] == [0, 1, 2, 3]


def test_rouge_l_beta_favours_recall():
    c = case()
    short = "refunds take"  # high precision, low recall
    f1 = run("rouge_l", short, c).score
    f_recall_heavy = run("rouge_l", short, c, {"beta": 3}).score
    assert f_recall_heavy < f1


def test_rouge_l_empty_answer():
    assert run("rouge_l", "", case()).score == 0.0


# ---------- length_ratio ----------

def test_length_ratio_inside_band():
    assert run("length_ratio", "one two three four five", case()).score == 1.0


def test_length_ratio_too_long_and_too_short():
    long_answer = " ".join(["word"] * 20)  # 20 vs 5 words -> x4, max 2 -> 0.5
    assert run("length_ratio", long_answer, case()).score == 0.5
    assert run("length_ratio", "one", case()).score == pytest.approx(0.4)


# ---------- no_forbidden ----------

def test_no_forbidden_uses_rubric_and_case_phrases():
    c = case(forbidden=["contact support"])
    params = {"phrases": ["as an ai language model"]}
    assert run("no_forbidden", "As an AI language model, no.", c, params).score == 0.0
    assert run("no_forbidden", "Please contact support.", c, params).score == 0.0
    assert run("no_forbidden", "Refunds take 5 days.", c, params).score == 1.0


def test_no_forbidden_not_applicable_when_empty():
    assert run("no_forbidden", "anything", case()).score is None


# ---------- plugin ----------

def test_numbers_match_catches_wrong_number():
    assert run("numbers_match", "Refunds take 7 business days.", case()).score == 0.0
    assert run("numbers_match", "About 5 business days.", case()).score == 1.0


def test_numbers_match_handles_commas():
    c = case(reference="Free delivery above 3,000 rupees.")
    assert run("numbers_match", "Orders over 3000 rupees ship free.", c).score == 1.0


# ---------- registry ----------

def test_registry_rejects_duplicates():
    with pytest.raises(ValueError):
        metrics.register("rouge_l", "again")(lambda a, c, p: None)


def test_unknown_metric_error_lists_known_ones():
    with pytest.raises(KeyError, match="rouge_l"):
        metrics.get_metric("bleu")


def test_new_metric_can_be_registered():
    @metrics.register("test_always_half", "test only")
    def half(answer, c, params):
        return metrics.MetricResult(0.5, "half")

    try:
        assert run("test_always_half", "x", case()).score == 0.5
    finally:
        del metrics.METRICS["test_always_half"]
