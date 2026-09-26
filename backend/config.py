"""
Settings for RubricSmith.

Everything comes from environment variables with safe defaults,
so the project runs right after cloning.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Default files used by the CLI, the API and the dashboard.
DEFAULT_DATASET = BASE_DIR / os.getenv("RUBRICSMITH_DATASET", "golden_dataset.jsonl")
DEFAULT_RUBRIC = BASE_DIR / os.getenv("RUBRICSMITH_RUBRIC", "rubric.json")

# Answer files must match this pattern to show up in the dashboard.
ANSWERS_GLOB = "answers_*.jsonl"

# SQLite file where finished runs are saved.
DB_PATH = Path(os.getenv("RUBRICSMITH_DB", str(BASE_DIR / "rubricsmith.db")))

# API server.
HOST = os.getenv("RUBRICSMITH_HOST", "127.0.0.1")
PORT = int(os.getenv("RUBRICSMITH_PORT", "8010"))
ALLOWED_ORIGIN = os.getenv("RUBRICSMITH_ALLOWED_ORIGIN", "http://localhost:3000")
MAX_BODY_BYTES = int(os.getenv("RUBRICSMITH_MAX_BODY_BYTES", str(2_000_000)))
