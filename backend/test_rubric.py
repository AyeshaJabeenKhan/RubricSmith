import json

import pytest

import metrics
from dataset import Case
from rubric import Rubric, RubricError


def make(metrics_cfg, threshold=0.6, plugins=None):
    return Rubric.from_dict({"name": "t", "pass_threshold": threshold,
                             "plugins": plugins or [], "metrics": metrics_cfg})


CASE = Case(id="c1", question="q", reference="Refunds take 5 business days.", keywords=["refund", "5 business days"])


def test_weighted_average():
    rubric = make({"exact_match": {"weight": 1}, "keyword_recall": {"weight": 3}})
    result = rubric.grade(CASE, "You get a refund.")  # exact 0, keywords 0.5 -> 1.5 / 4
    assert result.score == pytest.approx(0.375)
    assert not result.passed


def test_not_applicable_metric_is_left_out_of_the_average():
    rubric = make({"keyword_recall": {"weight": 5}, "rouge_l": {"weight": 1}})
    no_keywords = Case(id="c2", question="q", reference="Lahore")
    result = rubric.grade(no_keywords, "Lahore")
    assert result.score == 1.0  # only rouge_l counted


def test_minimum_is_a_hard_gate():
    rubric = make({"rouge_l": {"weight": 10}, "keyword_recall": {"weight": 1, "min": 1.0}}, threshold=0.5)
    result = rubric.grade(CASE, "Refunds take business days.")
    assert result.score >= 0.5
    assert not result.passed
    assert any("keyword_recall" in r for r in result.reasons)


def test_passing_case_has_no_reasons():
    rubric = make({"rouge_l": {"weight": 1}})
    result = rubric.grade(CASE, "Refunds take 5 business days.")
    assert result.passed and result.reasons == []


def test_broken_metric_fails_one_case_not_the_run():
    @metrics.register("test_broken", "raises")
    def broken(answer, c, params):
        raise RuntimeError("boom")

    try:
        result = make({"test_broken": {"weight": 1}}).grade(CASE, "x")
        assert result.score == 0.0
        assert "metric error: boom" in result.metrics[0].detail
    finally:
        del metrics.METRICS["test_broken"]


def test_plugins_are_loaded_by_name():
    rubric = make({"numbers_match": {"weight": 1}}, plugins=["plugin_numbers"])
    assert rubric.grade(CASE, "Refunds take 7 business days.").score == 0.0


@pytest.mark.parametrize("bad, message", [
    ({"metrics": {}}, "non-empty"),
    ({"metrics": {"bleu": {}}}, "Unknown metric"),
    ({"metrics": {"rouge_l": {"weight": -1}}}, "weight"),
    ({"metrics": {"rouge_l": {"weight": 0}}}, "above 0"),
    ({"metrics": {"rouge_l": {"min": 2}}}, "min"),
    ({"pass_threshold": 1.5, "metrics": {"rouge_l": {}}}, "pass_threshold"),
    ({"plugins": ["../evil"], "metrics": {"rouge_l": {}}}, "plain module name"),
    ({"plugins": ["no_such_plugin"], "metrics": {"rouge_l": {}}}, "Could not import"),
])
def test_invalid_rubrics_are_rejected(bad, message):
    with pytest.raises(RubricError, match=message):
        Rubric.from_dict(bad)


def test_load_reports_bad_json(tmp_path):
    path = tmp_path / "r.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(RubricError, match="not valid JSON"):
        Rubric.load(path)


def test_bundled_rubric_loads_and_round_trips():
    rubric = Rubric.load("rubric.json")
    again = Rubric.from_dict(json.loads(json.dumps(rubric.to_dict())))
    assert [r.name for r in again.rules] == [r.name for r in rubric.rules]
