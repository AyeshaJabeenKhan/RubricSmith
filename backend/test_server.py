import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import config
from server import ApiError, RubricSmithApp, make_handler
from storage import RunStore


@pytest.fixture
def app(tmp_path):
    return RubricSmithApp(store=RunStore(tmp_path / "t.db"))


def test_files_lists_answer_files(app):
    data = app.route("GET", "/api/files", {})
    assert data["dataset"] == "golden_dataset.jsonl"
    assert "answers_model_a.jsonl" in data["answers"]


def test_metrics_include_plugin(app):
    names = [m["name"] for m in app.route("GET", "/api/metrics", {})["metrics"]]
    assert "rouge_l" in names and "numbers_match" in names


def test_create_run_from_file_then_fetch(app):
    run = app.route("POST", "/api/runs", {"answers_file": "answers_model_a.jsonl"})
    assert run["summary"]["passed"] == 11
    fetched = app.route("GET", f"/api/runs/{run['id']}", {})
    assert fetched["cases"] == run["cases"]
    assert app.route("GET", "/api/runs", {})["runs"][0]["id"] == run["id"]


def test_create_run_from_text(app):
    text = '{"id": "cod", "answer": "Yes, cash on delivery is available for orders up to 20000 rupees."}'
    run = app.route("POST", "/api/runs", {"answers_text": text, "name": "pasted"})
    assert run["name"] == "pasted"
    assert run["summary"]["missing"] == 11


def test_path_traversal_is_blocked(app):
    with pytest.raises(ApiError) as err:
        app.route("POST", "/api/runs", {"answers_file": "../config.py"})
    assert err.value.status == 404


def test_bad_uploaded_answers_is_400(app):
    with pytest.raises(ApiError) as err:
        app.route("POST", "/api/runs", {"answers_text": "not json"})
    assert err.value.status == 400
    assert "uploaded answers:1: not valid JSON" in err.value.message


def test_scorecard_and_delete(app):
    run_id = app.route("POST", "/api/runs", {"answers_file": "answers_model_b.jsonl"})["id"]
    md = app.route("GET", f"/api/runs/{run_id}/scorecard", {})["markdown"]
    assert md.startswith("# Scorecard")
    app.route("DELETE", f"/api/runs/{run_id}", {})
    with pytest.raises(ApiError) as err:
        app.route("GET", f"/api/runs/{run_id}", {})
    assert err.value.status == 404


def test_run_id_must_be_a_number(app):
    with pytest.raises(ApiError) as err:
        app.route("GET", "/api/runs/abc", {})
    assert err.value.status == 400


def test_score_one(app):
    result = app.route("POST", "/api/score", {
        "reference": "Refunds take 5 business days.",
        "answer": "Refunds take 5 business days.",
        "keywords": ["refund"],
    })
    assert result["passed"] and result["score"] == 1.0


def test_score_one_validates_input(app):
    with pytest.raises(ApiError):
        app.route("POST", "/api/score", {"answer": "x"})
    with pytest.raises(ApiError):
        app.route("POST", "/api/score", {"reference": "x", "answer": "y", "keywords": "k"})


def test_broken_rubric_gives_clear_500(tmp_path):
    bad = tmp_path / "rubric.json"
    bad.write_text('{"metrics": {"bleu": {}}}', encoding="utf-8")
    app = RubricSmithApp(store=RunStore(tmp_path / "t.db"), rubric_path=bad)
    with pytest.raises(ApiError) as err:
        app.route("GET", "/api/rubric", {})
    assert err.value.status == 500 and "Unknown metric" in err.value.message


def test_real_http_round_trip(app):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        req = urllib.request.Request(f"{base}/api/runs", method="POST",
                                     data=json.dumps({"answers_file": "answers_model_a.jsonl"}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.headers["Access-Control-Allow-Origin"] == config.ALLOWED_ORIGIN
            assert json.loads(resp.read())["summary"]["total"] == 12

        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(f"{base}/api/nothing")
        assert err.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
