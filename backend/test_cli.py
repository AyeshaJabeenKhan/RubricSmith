import json

import pytest

import cli
import config


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "cli.db")


def test_run_prints_summary_and_writes_files(tmp_path, capsys):
    card, data = tmp_path / "card.md", tmp_path / "run.json"
    code = cli.main(["run", "--answers", "answers_model_a.jsonl", "--out", str(card), "--json", str(data)])
    out = capsys.readouterr().out
    assert code == 0
    assert "11/12 passed" in out
    assert card.read_text(encoding="utf-8").startswith("# Scorecard")
    assert json.loads(data.read_text(encoding="utf-8"))["summary"]["total"] == 12


def test_min_pass_rate_gate_fails_ci(capsys):
    assert cli.main(["run", "--answers", "answers_model_b.jsonl", "--min-pass-rate", "0.8"]) == 1
    assert "below --min-pass-rate" in capsys.readouterr().err


def test_save_then_list_runs(capsys):
    cli.main(["run", "--answers", "answers_model_a.jsonl", "--save"])
    cli.main(["runs"])
    out = capsys.readouterr().out
    assert "Saved as run #1" in out
    assert "#1" in out and "11/12 passed" in out


def test_runs_when_empty(capsys):
    cli.main(["runs"])
    assert "No saved runs yet" in capsys.readouterr().out


def test_score_single_answer(capsys):
    code = cli.main(["score", "--reference", "Refunds take 5 business days.",
                     "--answer", "Refunds take 7 business days.", "--keywords", "refund"])
    out = capsys.readouterr().out
    assert code == 1
    assert "missing numbers: 5" in out


def test_metrics_lists_plugin(capsys):
    cli.main(["metrics"])
    assert "numbers_match" in capsys.readouterr().out


def test_bad_input_returns_code_2(capsys):
    assert cli.main(["run", "--answers", "missing.jsonl"]) == 2
    assert "File not found" in capsys.readouterr().err
