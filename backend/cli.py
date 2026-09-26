"""
Command line tool.

  python cli.py run --answers answers_model_a.jsonl
  python cli.py run --answers answers_model_b.jsonl --out scorecard.md --save
  python cli.py run --answers my.jsonl --min-pass-rate 0.9      # exit code 1 if below, for CI
  python cli.py score --reference "Refunds take 5 days." --answer "Refunds take 7 days."
  python cli.py metrics
  python cli.py runs
"""

import argparse
import json
import sys

import config
from dataset import Case, DatasetError, load_answers, load_cases
from evaluator import evaluate
from metrics import list_metrics
from report import write_markdown
from rubric import Rubric, RubricError
from storage import RunStore


def cmd_run(args: argparse.Namespace) -> int:
    rubric = Rubric.load(args.rubric)
    cases = load_cases(args.dataset)
    answers = load_answers(args.answers)

    run = evaluate(cases, answers, rubric, name=args.name or "",
                   dataset_name=str(args.dataset).split("/")[-1],
                   answers_name=str(args.answers).split("/")[-1])
    s = run["summary"]

    for case in run["cases"]:
        mark = "PASS" if case["passed"] else "FAIL"
        note = "" if case["passed"] else f"  ({case['reasons'][0]})"
        print(f"  {mark}  {case['score']:.2f}  {case['id']}{note}")

    print(f"\n{s['passed']}/{s['total']} passed ({s['pass_rate'] * 100:.0f}%), mean score {s['mean_score']:.2f}")
    for warning in run["warnings"]:
        print(f"Warning: {warning}")

    if args.out:
        print(f"Scorecard written to {write_markdown(run, args.out)}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(run, f, indent=2)
        print(f"JSON written to {args.json}")
    if args.save:
        print(f"Saved as run #{RunStore(config.DB_PATH).save(run)}")

    if args.min_pass_rate is not None and s["pass_rate"] < args.min_pass_rate:
        print(f"Pass rate {s['pass_rate']:.2f} is below --min-pass-rate {args.min_pass_rate:.2f}", file=sys.stderr)
        return 1
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else []
    case = Case(id="cli", question="", reference=args.reference, keywords=keywords)
    result = Rubric.load(args.rubric).grade(case, args.answer)

    for m in result.metrics:
        score = "  n/a" if m.score is None else f"{m.score:5.2f}"
        flag = "  below min" if m.below_minimum else ""
        print(f"  {m.name:<15} {score}  {m.detail}{flag}")
    print(f"\nScore {result.score:.2f}: {'PASS' if result.passed else 'FAIL'}")
    for reason in result.reasons:
        print(f"  - {reason}")
    return 0 if result.passed else 1


def cmd_metrics(args: argparse.Namespace) -> int:
    Rubric.load(args.rubric)  # loads plugin metrics too
    for m in list_metrics():
        print(f"  {m['name']:<15} {m['description']}")
    return 0


def cmd_runs(args: argparse.Namespace) -> int:
    runs = RunStore(config.DB_PATH).list()
    if not runs:
        print("No saved runs yet. Use: python cli.py run --answers <file> --save")
        return 0
    for r in runs:
        print(f"  #{r['id']:<4} {r['created_at']}  {r['passed']}/{r['total']} passed  "
              f"mean {r['mean_score']:.2f}  {r['name']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rubricsmith", description="Grade LLM answers against a golden dataset.")
    parser.add_argument("--rubric", default=str(config.DEFAULT_RUBRIC), help="rubric JSON file")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="grade a whole answers file")
    run.add_argument("--answers", required=True, help="answers JSONL file")
    run.add_argument("--dataset", default=str(config.DEFAULT_DATASET), help="golden dataset JSONL file")
    run.add_argument("--name", help="a name for this run")
    run.add_argument("--out", help="write the Markdown scorecard here")
    run.add_argument("--json", help="write the full result as JSON here")
    run.add_argument("--save", action="store_true", help="save the run so the dashboard shows it")
    run.add_argument("--min-pass-rate", type=float, help="exit with code 1 if the pass rate is lower")
    run.set_defaults(func=cmd_run)

    score = sub.add_parser("score", help="grade one answer")
    score.add_argument("--reference", required=True)
    score.add_argument("--answer", required=True)
    score.add_argument("--keywords", help="comma separated, e.g. 'refund,5 business days'")
    score.set_defaults(func=cmd_score)

    sub.add_parser("metrics", help="list available metrics").set_defaults(func=cmd_metrics)
    sub.add_parser("runs", help="list saved runs").set_defaults(func=cmd_runs)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (DatasetError, RubricError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
