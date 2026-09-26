"""
Loading the golden dataset and the model answers.

Both are JSONL: one JSON object per line.

golden_dataset.jsonl
  {"id": "refund-01", "question": "...", "reference": "...",
   "keywords": ["refund", "5 business days"], "aliases": [], "tags": ["billing"]}

answers_<model>.jsonl
  {"id": "refund-01", "answer": "..."}

Errors always include the file and line number, because "invalid JSON"
with no line number is painful when the file has 500 lines.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path


class DatasetError(Exception):
    """Raised when a JSONL file is missing fields or is not valid JSON."""


@dataclass
class Case:
    id: str
    question: str
    reference: str
    keywords: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


def parse_jsonl(text: str, source: str = "<text>") -> list[tuple[int, dict]]:
    """Parse JSONL text. Returns (line_number, object) pairs. Blank lines are skipped."""
    rows = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetError(f"{source}:{line_no}: not valid JSON ({exc.msg})") from exc
        if not isinstance(obj, dict):
            raise DatasetError(f"{source}:{line_no}: each line must be a JSON object")
        rows.append((line_no, obj))
    return rows


def _string_list(obj: dict, key: str, where: str) -> list[str]:
    value = obj.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise DatasetError(f"{where}: '{key}' must be a list of strings")
    return value


def _require_string(obj: dict, key: str, where: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DatasetError(f"{where}: '{key}' is required and must be a non-empty string")
    return value


def parse_cases(text: str, source: str = "<dataset>") -> list[Case]:
    cases: list[Case] = []
    seen: set[str] = set()

    for line_no, obj in parse_jsonl(text, source):
        where = f"{source}:{line_no}"
        case_id = _require_string(obj, "id", where)
        if case_id in seen:
            raise DatasetError(f"{where}: duplicate id '{case_id}'")
        seen.add(case_id)

        cases.append(Case(
            id=case_id,
            question=_require_string(obj, "question", where),
            reference=_require_string(obj, "reference", where),
            keywords=_string_list(obj, "keywords", where),
            aliases=_string_list(obj, "aliases", where),
            forbidden=_string_list(obj, "forbidden", where),
            tags=_string_list(obj, "tags", where),
        ))

    if not cases:
        raise DatasetError(f"{source}: dataset is empty")
    return cases


def parse_answers(text: str, source: str = "<answers>") -> dict[str, str]:
    answers: dict[str, str] = {}
    for line_no, obj in parse_jsonl(text, source):
        where = f"{source}:{line_no}"
        case_id = _require_string(obj, "id", where)
        answer = obj.get("answer")
        if not isinstance(answer, str):
            raise DatasetError(f"{where}: 'answer' must be a string")
        if case_id in answers:
            raise DatasetError(f"{where}: duplicate id '{case_id}'")
        answers[case_id] = answer
    return answers


def load_cases(path: Path | str) -> list[Case]:
    path = Path(path)
    return parse_cases(_read(path), path.name)


def load_answers(path: Path | str) -> dict[str, str]:
    path = Path(path)
    return parse_answers(_read(path), path.name)


def _read(path: Path) -> str:
    if not path.exists():
        raise DatasetError(f"File not found: {path}")
    return path.read_text(encoding="utf-8")
