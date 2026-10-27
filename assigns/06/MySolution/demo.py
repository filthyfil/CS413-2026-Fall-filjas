"""Command-line demonstration: run every example through the whole pipeline.

From assigns/06:
    python3.12 MySolution/demo.py
    python3.12 MySolution/demo.py --exec-budget 50000 --obs-budget 50000
    python3.12 MySolution/demo.py --full          # print complete terms
    python3.12 MySolution/demo.py --only fact     # examples whose label matches

For each example this prints the source, the generated pure term (shortened
on screen; the complete term is saved under MySolution/demo_output/), the
execution outcome and beta-value step count, the observation outcome and
its separate step count, the decoded answer, the explicit expected answer,
and, for terminating examples, the shared evaluator's source-side result.
The exit status is 0 when every example matches its expectation.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from demo_examples import DIVERGES, EXAMPLES, Example  # noqa: E402
from evaluator import evaluate_source, source_result  # noqa: E402
from pipeline import (  # noqa: E402
    DEFAULT_EXEC_BUDGET, DEFAULT_OBS_BUDGET, format_kind, format_value,
    run_pipeline,
)
from source_visitors import d0exp_pretty  # noqa: E402
from target import term_print  # noqa: E402

SHOW_CHARS = 160


def slug(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", label.split("  ")[0]).strip("_").lower()


def run_example(index: int, ex: Example, args, out_dir: Path) -> bool:
    result = run_pipeline(ex.source, ex.kind, args.exec_budget, args.obs_budget)
    term_text = term_print(result.term)
    path = out_dir / f"{index:02d}_{slug(ex.label)}.txt"
    path.write_text(f"# {ex.label}\n# source: {d0exp_pretty(ex.source)}\n"
                    f"# {len(term_text)} characters\n{term_text}\n")

    print(f"[{index:02d}] {ex.label}")
    print(f"  source       : {d0exp_pretty(ex.source)}")
    if args.full or len(term_text) <= SHOW_CHARS:
        print(f"  target       : {term_text}")
    else:
        print(f"  target       : {term_text[:SHOW_CHARS]}...")
    print(f"                 ({len(term_text)} chars; saved to {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path})")

    ex_steps = result.execution.steps
    if result.execution.completed:
        print(f"  execution    : value after {ex_steps} beta-value steps "
              f"(budget {args.exec_budget})")
    else:
        print(f"  execution    : budget exhausted after {ex_steps} beta-value steps "
              f"(budget {args.exec_budget}; not a proof of divergence)")

    obs = result.observation
    if obs is None:
        print("  observation  : not run (execution did not complete)")
    else:
        detail = f": {obs.detail}" if obs.detail else ""
        print(f"  observation  : {obs.status} as {format_kind(ex.kind)} after "
              f"{obs.steps} beta-value steps (budget {args.obs_budget}){detail}")

    decoded = format_value(result.value) if result.decoded else "-"
    expected = ex.expected if ex.expected == DIVERGES else format_value(ex.expected)
    print(f"  decoded      : {decoded}")
    print(f"  expected     : {expected}")

    if ex.expected == DIVERGES:
        passed = not result.execution.completed
    else:
        source_value = source_result(evaluate_source(ex.source).term)
        print(f"  source eval  : {format_value(source_value)}")
        passed = (result.decoded and result.value == ex.expected
                  and source_value == ex.expected)
    print(f"  result       : {'PASS' if passed else 'FAIL'}\n")
    return passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--exec-budget", type=int, default=DEFAULT_EXEC_BUDGET,
                        help=f"beta-value steps for execution (default {DEFAULT_EXEC_BUDGET})")
    parser.add_argument("--obs-budget", type=int, default=DEFAULT_OBS_BUDGET,
                        help=f"beta-value steps for observation (default {DEFAULT_OBS_BUDGET})")
    parser.add_argument("--out", type=Path, default=HERE / "demo_output",
                        help="directory for the generated terms")
    parser.add_argument("--full", action="store_true", help="print complete terms")
    parser.add_argument("--only", default="", help="run examples whose label contains this")
    args = parser.parse_args(argv)
    if args.exec_budget < 0 or args.obs_budget < 0:
        parser.error("budgets must be nonnegative")
    args.out.mkdir(parents=True, exist_ok=True)

    print(f"Execution budget: {args.exec_budget} beta-value steps; "
          f"observation budget: {args.obs_budget} beta-value steps.\n")
    selected = [(i, ex) for i, ex in enumerate(EXAMPLES, 1) if args.only in ex.label]
    totals = {}
    for required, title in ((True, "Required demonstrations"),
                            (False, "Additional examples (beyond the required table)")):
        group = [(i, ex) for i, ex in selected if ex.required == required]
        if not group:
            continue
        print(f"=== {title} ===\n")
        totals[title] = (sum(run_example(i, ex, args, args.out) for i, ex in group),
                         len(group))
    for title, (passed, count) in totals.items():
        print(f"{title}: {passed}/{count} matched their expected results.")
    return 0 if all(p == c for p, c in totals.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
