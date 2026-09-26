"""
Saves finished runs in a small SQLite file (standard library sqlite3).

Only the summary numbers get their own columns, so the run list is
quick to load. The full result is stored as JSON in one column.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    dataset     TEXT,
    answers     TEXT,
    rubric_name TEXT,
    total       INTEGER NOT NULL,
    passed      INTEGER NOT NULL,
    pass_rate   REAL NOT NULL,
    mean_score  REAL NOT NULL,
    result_json TEXT NOT NULL
)
"""

SUMMARY_COLUMNS = "id, name, created_at, dataset, answers, rubric_name, total, passed, pass_rate, mean_score"


class RunStore:
    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)
        with self._connect() as conn:
            conn.execute(SCHEMA)

    @contextmanager
    def _connect(self):
        # One short connection per call. Simple, and safe with the threaded server.
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save(self, run: dict) -> int:
        summary = run["summary"]
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO runs (name, created_at, dataset, answers, rubric_name, total, passed, "
                "pass_rate, mean_score, result_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run["name"], run["created_at"], run.get("dataset"), run.get("answers"),
                    run["rubric"]["name"], summary["total"], summary["passed"],
                    summary["pass_rate"], summary["mean_score"], json.dumps(run),
                ),
            )
            return cursor.lastrowid

    def list(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {SUMMARY_COLUMNS} FROM runs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, run_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT id, result_json FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        run = json.loads(row["result_json"])
        run["id"] = row["id"]
        return run

    def delete(self, run_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
            return cursor.rowcount > 0
