from dataset import Case, load_answers, load_cases
from evaluator import evaluate
from rubric import Rubric

RUBRIC = Rubric.from_dict({"pass_threshold": 0.5, "metrics": {"rouge_l": {"weight": 1}}})
CASES = [
    Case(id="a", question="q", reference="open my orders", tags=["x"]),
    Case(id="b", question="q", reference="tap forgot password", tags=["x", "y"]),
    Case(id="c", question="q", reference="call us"),
]


def test_summary_counts():
    run = evaluate(CASES, {"a": "open my orders", "b": "no idea"}, RUBRIC)
    s = run["summary"]
    assert (s["total"], s["passed"], s["failed"], s["missing"]) == (3, 1, 2, 1)
    assert s["pass_rate"] == round(1 / 3, 4)


def test_missing_answer_fails_with_reason():
    run = evaluate(CASES, {}, RUBRIC)
    assert all(c["reasons"] == ["no answer for this case"] for c in run["cases"])
    assert run["summary"]["fail_causes"]["missing answer"] == 3


def test_extra_answers_become_a_warning():
    run = evaluate(CASES, {"a": "x", "zzz": "y"}, RUBRIC)
    assert "zzz" in run["warnings"][0]


def test_by_tag_and_untagged():
    run = evaluate(CASES, {"a": "open my orders", "b": "tap forgot password", "c": "no"}, RUBRIC)
    tags = run["summary"]["by_tag"]
    assert tags["x"] == {"total": 2, "passed": 2, "pass_rate": 1.0}
    assert tags["untagged"]["passed"] == 0


def test_run_is_plain_json_friendly():
    import json
    run = evaluate(CASES, {"a": "open my orders"}, RUBRIC, name="demo")
    assert json.loads(json.dumps(run))["name"] == "demo"


def test_sample_models_rank_as_expected():
    rubric = Rubric.load("rubric.json")
    cases = load_cases("golden_dataset.jsonl")
    good = evaluate(cases, load_answers("answers_model_a.jsonl"), rubric)["summary"]
    weak = evaluate(cases, load_answers("answers_model_b.jsonl"), rubric)["summary"]
    assert good["pass_rate"] > weak["pass_rate"]
    assert good["mean_score"] > weak["mean_score"]
