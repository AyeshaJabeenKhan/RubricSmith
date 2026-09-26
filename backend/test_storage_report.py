import pytest

from dataset import load_answers, load_cases
from evaluator import evaluate
from report import cell, to_markdown, write_markdown
from rubric import Rubric
from storage import RunStore


@pytest.fixture(scope="module")
def run_b():
    rubric = Rubric.load("rubric.json")
    return evaluate(load_cases("golden_dataset.jsonl"), load_answers("answers_model_b.jsonl"), rubric,
                    dataset_name="golden_dataset.jsonl", answers_name="answers_model_b.jsonl")


# ---------- storage ----------

def test_save_list_get_delete(tmp_path, run_b):
    store = RunStore(tmp_path / "t.db")
    first = store.save(run_b)
    second = store.save(run_b)

    listed = store.list()
    assert [r["id"] for r in listed] == [second, first]  # newest first
    assert listed[0]["passed"] == run_b["summary"]["passed"]

    loaded = store.get(first)
    assert loaded["id"] == first
    assert loaded["cases"] == run_b["cases"]

    assert store.delete(first)
    assert store.get(first) is None
    assert not store.delete(first)


def test_list_does_not_load_full_results(tmp_path, run_b):
    store = RunStore(tmp_path / "t.db")
    store.save(run_b)
    assert "cases" not in store.list()[0]


# ---------- report ----------

def test_scorecard_has_summary_tables_and_failures(run_b):
    md = to_markdown(run_b)
    assert md.startswith("# Scorecard: answers_model_b.jsonl")
    assert "4 of 12 cases passed (33%)" in md
    assert "| rouge_l | 3 | - |" in md
    assert "### ❌ refund-time" in md
    assert "numbers_match 0.00 is below its minimum 1.00" in md
    assert "> Warning:" in md


def test_scorecard_marks_not_applicable_metrics(run_b):
    row = next(line for line in to_markdown(run_b).splitlines() if "| capital-city |" in line)
    assert " - " in row  # keyword_recall does not apply to this case


def test_cell_escapes_pipes_and_shortens():
    assert cell("a | b") == "a \\| b"
    assert len(cell("x" * 100, limit=20)) == 20


def test_all_pass_scorecard(tmp_path):
    rubric = Rubric.load("rubric.json")
    cases = load_cases("golden_dataset.jsonl")[:1]
    run = evaluate(cases, {cases[0].id: cases[0].reference}, rubric)
    path = write_markdown(run, tmp_path / "card.md")
    text = path.read_text(encoding="utf-8")
    assert "**Result: PASS.**" in text
    assert "Why cases failed" not in text
