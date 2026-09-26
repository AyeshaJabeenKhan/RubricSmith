import pytest

from dataset import DatasetError, load_answers, load_cases, parse_answers, parse_cases


def test_parse_cases_with_optional_fields():
    cases = parse_cases('{"id": "a", "question": "q", "reference": "r", "keywords": ["k"], "tags": ["t"]}\n\n')
    assert cases[0].keywords == ["k"] and cases[0].tags == ["t"] and cases[0].aliases == []


@pytest.mark.parametrize("text, message", [
    ('{"id": "a", "question": "q"}', "'reference' is required"),
    ('{"id": "a", "question": "q", "reference": "r", "keywords": "k"}', "list of strings"),
    ('not json', "line 1|:1: not valid JSON"),
    ('[1, 2]', "JSON object"),
    ('', "empty"),
])
def test_bad_datasets_give_clear_errors(text, message):
    with pytest.raises(DatasetError, match=message):
        parse_cases(text, "data.jsonl")


def test_error_includes_line_number():
    text = '{"id": "a", "question": "q", "reference": "r"}\n{"id": "a", "question": "q", "reference": "r"}'
    with pytest.raises(DatasetError, match="data.jsonl:2: duplicate id 'a'"):
        parse_cases(text, "data.jsonl")


def test_parse_answers():
    assert parse_answers('{"id": "a", "answer": "yes"}') == {"a": "yes"}
    with pytest.raises(DatasetError, match="'answer' must be a string"):
        parse_answers('{"id": "a", "answer": 5}')


def test_missing_file():
    with pytest.raises(DatasetError, match="File not found"):
        load_cases("nope.jsonl")


def test_bundled_files_load():
    cases = load_cases("golden_dataset.jsonl")
    answers = load_answers("answers_model_a.jsonl")
    assert len(cases) == 12
    assert set(answers) == {c.id for c in cases}
