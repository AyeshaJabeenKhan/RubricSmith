"""
RubricSmith HTTP API, built on the standard library only.

Run:  python server.py   (listens on http://127.0.0.1:8010)

Endpoints
  GET    /api/health
  GET    /api/metrics                 registered metrics
  GET    /api/rubric                  the default rubric
  GET    /api/files                   dataset and answer files you can run
  GET    /api/runs                    saved runs, newest first
  POST   /api/runs                    {"answers_file"} or {"answers_text", "name"}
  GET    /api/runs/<id>               one run with every case
  GET    /api/runs/<id>/scorecard     the Markdown scorecard
  DELETE /api/runs/<id>
  POST   /api/score                   grade one answer: {"reference", "answer", "keywords"?}
"""

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config
from dataset import Case, DatasetError, load_answers, load_cases, parse_answers
from evaluator import evaluate
from metrics import list_metrics
from report import to_markdown
from rubric import Rubric, RubricError
from storage import RunStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rubricsmith")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class RubricSmithApp:
    """API logic, kept apart from HTTP so tests can call it directly."""

    def __init__(self, store: RunStore | None = None, dataset_path=config.DEFAULT_DATASET,
                 rubric_path=config.DEFAULT_RUBRIC, base_dir=config.BASE_DIR):
        self.store = store or RunStore(config.DB_PATH)
        self.dataset_path = dataset_path
        self.rubric_path = rubric_path
        self.base_dir = base_dir

    # ----- helpers -----

    def _rubric(self) -> Rubric:
        try:
            return Rubric.load(self.rubric_path)
        except RubricError as exc:
            raise ApiError(500, f"Rubric problem: {exc}") from exc

    def _cases(self) -> list[Case]:
        try:
            return load_cases(self.dataset_path)
        except DatasetError as exc:
            raise ApiError(500, f"Dataset problem: {exc}") from exc

    def _answer_files(self) -> list[str]:
        return sorted(p.name for p in self.base_dir.glob(config.ANSWERS_GLOB))

    def _run_id(self, raw: str) -> int:
        if not raw.isdigit():
            raise ApiError(400, "Run id must be a number.")
        return int(raw)

    # ----- handlers -----

    def health(self) -> dict:
        return {"status": "ok", "runs": len(self.store.list(limit=1000))}

    def metrics(self) -> dict:
        self._rubric()  # loads plugins so their metrics show up too
        return {"metrics": list_metrics()}

    def rubric(self) -> dict:
        return self._rubric().to_dict()

    def files(self) -> dict:
        return {"dataset": self.dataset_path.name, "answers": self._answer_files()}

    def list_runs(self) -> dict:
        return {"runs": self.store.list()}

    def create_run(self, body: dict) -> dict:
        answers_file = body.get("answers_file")
        answers_text = body.get("answers_text")

        try:
            if answers_file:
                # Only files from the list are allowed. This blocks paths like "../../etc/passwd".
                if answers_file not in self._answer_files():
                    raise ApiError(404, f"Unknown answers file '{answers_file}'.")
                answers = load_answers(self.base_dir / answers_file)
                answers_name = answers_file
            elif isinstance(answers_text, str) and answers_text.strip():
                answers = parse_answers(answers_text, "uploaded answers")
                answers_name = str(body.get("name") or "uploaded answers")
            else:
                raise ApiError(400, "Send 'answers_file' or 'answers_text'.")
        except DatasetError as exc:
            raise ApiError(400, str(exc)) from exc

        run = evaluate(self._cases(), answers, self._rubric(),
                       name=str(body.get("name") or answers_name),
                       dataset_name=self.dataset_path.name, answers_name=answers_name)
        run["id"] = self.store.save(run)
        log.info("Run %s saved: %s passed %s/%s", run["id"], answers_name,
                 run["summary"]["passed"], run["summary"]["total"])
        return run

    def get_run(self, raw_id: str) -> dict:
        run = self.store.get(self._run_id(raw_id))
        if run is None:
            raise ApiError(404, "Run not found.")
        return run

    def scorecard(self, raw_id: str) -> dict:
        return {"markdown": to_markdown(self.get_run(raw_id))}

    def delete_run(self, raw_id: str) -> dict:
        if not self.store.delete(self._run_id(raw_id)):
            raise ApiError(404, "Run not found.")
        return {"deleted": int(raw_id)}

    def score_one(self, body: dict) -> dict:
        reference, answer = body.get("reference"), body.get("answer")
        if not isinstance(reference, str) or not reference.strip():
            raise ApiError(400, "'reference' is required.")
        if not isinstance(answer, str):
            raise ApiError(400, "'answer' must be a string.")
        keywords = body.get("keywords") or []
        if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
            raise ApiError(400, "'keywords' must be a list of strings.")

        case = Case(id="playground", question=str(body.get("question") or ""), reference=reference, keywords=keywords)
        return self._rubric().grade(case, answer).to_dict()

    # ----- routing -----

    def route(self, method: str, path: str, body: dict) -> dict:
        path = path.split("?", 1)[0].rstrip("/")
        simple = {
            ("GET", "/api/health"): self.health,
            ("GET", "/api/metrics"): self.metrics,
            ("GET", "/api/rubric"): self.rubric,
            ("GET", "/api/files"): self.files,
            ("GET", "/api/runs"): self.list_runs,
            ("POST", "/api/runs"): lambda: self.create_run(body),
            ("POST", "/api/score"): lambda: self.score_one(body),
        }
        if (method, path) in simple:
            return simple[(method, path)]()

        parts = path.split("/")  # ["", "api", "runs", "<id>", "scorecard"?]
        if len(parts) >= 4 and parts[:3] == ["", "api", "runs"]:
            run_id = parts[3]
            if len(parts) == 4 and method == "GET":
                return self.get_run(run_id)
            if len(parts) == 4 and method == "DELETE":
                return self.delete_run(run_id)
            if len(parts) == 5 and parts[4] == "scorecard" and method == "GET":
                return self.scorecard(run_id)

        raise ApiError(404, f"No route for {method} {path}")


def make_handler(app: RubricSmithApp):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: dict) -> None:
            data = b"" if status == 204 else json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", config.ALLOWED_ORIGIN)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            if data:
                self.wfile.write(data)

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length == 0:
                return {}
            if length > config.MAX_BODY_BYTES:
                raise ApiError(413, "Request body is too large.")
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise ApiError(400, "Body must be valid JSON.")
            if not isinstance(body, dict):
                raise ApiError(400, "Body must be a JSON object.")
            return body

        def _handle(self, method: str) -> None:
            try:
                body = self._read_body() if method == "POST" else {}
                self._send(200, app.route(method, self.path, body))
            except ApiError as exc:
                self._send(exc.status, {"error": exc.message})
            except Exception:
                log.exception("Unhandled error")
                self._send(500, {"error": "Internal server error."})

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def do_DELETE(self):
            self._handle("DELETE")

        def do_OPTIONS(self):
            self._send(204, {})

        def log_message(self, fmt, *args):
            log.info("%s - %s", self.address_string(), fmt % args)

    return Handler


def main() -> None:
    app = RubricSmithApp()
    server = ThreadingHTTPServer((config.HOST, config.PORT), make_handler(app))
    log.info("RubricSmith API on http://%s:%s", config.HOST, config.PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
