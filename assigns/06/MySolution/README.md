# Midterm 1 (Assignment 6): Compiling Extended LAMBDA into Pure Lambda-Calculus

This project compiles extended LAMBDA source ASTs (naturals, booleans,
arithmetic, comparisons, conditionals, `let`, pairs, recursion) into Church's
pure lambda-calculus. The output contains only variables, one-parameter
lambdas and applications. A step-bounded call-by-value reducer runs the
output, and pure observation contexts decode the result. The same evaluator
also runs source ASTs, and the demo compares those results with the decoded
ones.

The design, the translation rules and the correctness argument are in
[`DESIGN.md`](DESIGN.md). AI use is recorded in
[`AI-TRANSCRIPT.md`](AI-TRANSCRIPT.md).

## Presentation

| Deliverable | Location |
| --- | --- |
| Slides (PDF, 28 slides) | [`slides.pdf`](slides.pdf) |
| Video recording (`fj-assign06ppt.mp4`, Google Drive) | <https://drive.google.com/file/d/17Ma7ooV19egr4PbU3bsO7qStdx00r12z/view?usp=sharing> |

The video is hosted on Google Drive because it is too large for the
submission. Anyone with the link can view it; no permission request is
needed.

## Requirements

| Needed for | Software | Tested with |
| --- | --- | --- |
| Compiler, tests, demo (graded core) | Python 3.12 or later, standard library only | Python 3.12.14 |
| Web front-end (optional extension) | Flask 3 | Flask 3.1.3 |
| Static type check (optional) | mypy 1.11 or later | mypy 2.4.0 |

Python 3.12 is required because the supplied `lambda1_vp.py` uses the `type`
statement. On my machine `python3` is 3.10, so every command below names
`python3.12` explicitly.

## Setup, tests, and demo

Run everything from `assigns/06/`.

The graded core needs only the standard library, so no setup is required:

```sh
python3.12 -m unittest discover -s MySolution -p 'test_*.py'      # core suite (137 tests, ~8 s)
python3.12 MySolution/demo.py                                      # all demonstrations (~10-15 s)
```

Demo options:

```sh
python3.12 MySolution/demo.py --exec-budget 50000 --obs-budget 50000
python3.12 MySolution/demo.py --only fact --full    # examples whose label contains "fact", full terms
```

The extensions need Flask, installed in a virtual environment:

```sh
python3.12 -m venv .venv
.venv/bin/pip install flask
.venv/bin/python -m unittest discover -s MySolution/extensions -p 'test_*.py'   # 19 tests
.venv/bin/python MySolution/extensions/web/serve.py      # then open http://127.0.0.1:5000/
```

Without Flask the extension suite still runs and skips its 11 web tests. The
`.venv/` directory sits outside `MySolution/` and is not part of the
submission.

To type-check the Python code (the configuration is in `MySolution/mypy.ini`):

```sh
.venv/bin/pip install mypy
.venv/bin/mypy --config-file MySolution/mypy.ini MySolution/*.py
MYPYPATH=MySolution:MySolution/extensions:MySolution/extensions/web \
  .venv/bin/mypy --config-file MySolution/mypy.ini MySolution/extensions/*.py \
  MySolution/extensions/web/server/*.py MySolution/extensions/web/serve.py
```

Both report no issues. mypy checks the Python code only. It does not
type-check LAMBDA programs (see [Limitations](#limitations)). The supplied
`lambda1_vp.py` is excluded from the error report because it may not be
modified.

## Module overview

Graded core (`MySolution/`):

| Module | Role |
| --- | --- |
| `lambda1_vp.py` | The supplied source AST and `D0ExpVisitor`: an unmodified copy of `assigns/05/lambda1_vp.py`. `test_source_copy.py` checks that it is byte-identical. |
| `source_ast.py` | The one place the rest of the code imports the source AST from |
| `source_visitors.py` | Reused from my Assignment 5: pretty printer, all-names visitor, `FreshNames`, source substitution |
| `target.py` | Target AST `Var`/`Lam`/`App`, printer, free variables, capture-avoiding substitution, alpha-equivalence |
| `evaluator.py` | The shared evaluator: one call-by-value machine for source ASTs and target terms, with step budgets |
| `church.py` | Church-encoding library: closed combinators for booleans, pairs, naturals, arithmetic, comparisons, `Z` |
| `observe.py` | Bounded observers that decode naturals, booleans and nested pairs |
| `compiler.py` | `compile_expr`: the compiler as a `D0ExpVisitor` |
| `pipeline.py` | Compile → execute → observe, with separate budgets. Used by the demo and the web front-end |
| `demo_examples.py`, `demo.py` | The demonstration programs and the command-line runner |
| `test_*.py` | `unittest` suites, mapped to the assignment's obligations in [Testing](#testing) |

The dependencies between modules go one way. `test_modules.py` checks that
the compiler does not import the evaluator, that the evaluator does not
import the compiler or `church.py`, and that nothing in the core imports
`extensions/`.

## Interfaces and outcomes

| Operation | Call | Success | Other outcomes |
| --- | --- | --- | --- |
| Compile | `compiler.compile_expr(e)` | pure `Term`, also for open `e` | `CompileError` naming the negative literal, unsupported operator or bad identifier |
| Print | `target.term_print(t)` | `x`, `(lam x. body)`, `(fn arg)` | — |
| Free variables | `target.free_vars(t)` | `frozenset` of names | — |
| Substitute | `target.substitute(t, x, r)` | capture-avoiding `t[x := r]` | — |
| Evaluate | `evaluator.evaluate(p, budget=None)` | `Reduction(status="value", term, steps)` | `Reduction(status="exhausted", term=residual, steps)`; `OpenTermError` for open programs; `SourceError` for source runtime errors |
| Reduce target | `evaluator.reduce_term(t, budget)` | as above, target terms only, budget required | as above |
| Observe | `observe.observe(v, kind, budget)` with `kind` = `"nat"`, `"bool"` or a pair of kinds | `Observation(status="decoded", value, steps)` | `status="exhausted"` or `status="malformed"` with a `detail` message |
| Pipeline | `pipeline.run_pipeline(e, kind, exec_budget, obs_budget)` | `PipelineResult` with the term, the execution `Reduction` and the `Observation` | observation is `None` when execution was exhausted |

How statuses are represented:

- **Execution** reports `value` or `exhausted` together with the number of
  beta-value steps. A value completes in 0 steps, even with budget 0. A value
  reached on the last allowed step counts as completed. `exhausted` means
  another step was needed after the budget ran out. It is not a proof of
  nontermination.
- **Observation** reports `decoded`, `exhausted` or `malformed`, with its
  own step count. The caller always states the expected kind, because
  `NUM(0)` and `FALSE` are the same term.
- **Errors** are exceptions. `CompileError` comes from the compiler,
  `OpenTermError` from the evaluator when the program has free variables,
  `SourceError` from source-side runtime errors such as `if` on a number, and
  `ValueError` from an invalid budget.

## Budgets

Execution and observation have separate budgets and separate step counts.
Both default to **100,000 beta-value steps**, which is far more than any
terminating demonstration needs: the largest is `fib 5` at 2,021 execution
steps. The diverging examples use their whole budget. Source-side
evaluation is unbounded, as the assignment allows, and runs only for the
terminating examples.

## Results

Output of `python3.12 MySolution/demo.py` with the default budgets. Every
terminating row also matches the shared evaluator's source-side result.

| # | Source | Term size (chars) | Execution | Observation | Decoded | Expected |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `2 + 3 * 4` | 194 | value, 4 steps | decoded, 25 steps | 14 | 14 |
| 2 | `2 - 5` | 395 | value, 87 | decoded, 2 | 0 | 0 |
| 3 | `if 2 <= 3 then 7 else 9` | 622 | value, 77 | decoded, 9 | 7 | 7 |
| 4 | `let x = 3 in (lam y. x + y) 4` | 151 | value, 4 | decoded, 13 | 7 | 7 |
| 5 | `fst (pair 2 true)` | 123 | value, 6 | decoded, 4 | 2 | 2 |
| 6 | `snd (pair 2 true)` | 123 | value, 6 | decoded, 2 | true | true |
| 7 | `(lam f. f 3) (lam x. x + 1)` | 139 | value, 4 | decoded, 10 | 4 | 4 |
| 8 | `true and false` | 98 | value, 3 | decoded, 2 | false | false |
| 9 | `false or true` | 98 | value, 3 | decoded, 2 | true | true |
| 10 | `if true then 1 else LOOP` | 211 | value, 3 | decoded, 3 | 1 | 1 |
| 11 | `(lam x. 0) LOOP` | 159 | exhausted, 100000 | not run | — | exhaustion |
| 12 | `fact 4` | 1544 | value, 471 | decoded, 218 | 24 | 24 |
| 13 | `fib 5` | 1494 | value, 2021 | decoded, 45 | 5 | 5 |
| 14 | `LOOP` | 128 | exhausted, 100000 | not run | — | exhaustion |

Rows 1–14 are the required demonstrations. The demo also runs six
additional examples: a nested pair, `(fix f(f). f) 3`, `false and LOOP`,
`not (3 != 3)`, encoding names used as source names, and
`let x = LOOP in 2`. All six match their expected results. The complete
generated terms are saved to `MySolution/demo_output/`, which every demo run
regenerates.

Most of the arithmetic in row 1 happens during observation. Execution stops
as soon as the result is a lambda, so `ADD 2 (MUL 3 4)` becomes a lambda whose
body still holds the multiplication. That work runs only when the observer
applies the value to `STEP` and `BASE`.

## Testing

All suites use `unittest` and state their expected results explicitly.

| Assignment obligation | Where it is tested |
| --- | --- |
| 1. Substitution with shadowing and capture hazards (`[x := y](lam y. x)`) | `test_target.py` `SubstitutionTests` |
| 2. Left-to-right CBV, no reduction under lambdas, zero-step values, determinism, budget exhaustion | `test_reducer.py` (incl. ACC-02, ACC-03, ACC-04) |
| 3. Every constructor and operator, zero, pred 0, both comparison outcomes, truth tables | `test_church.py` (each encoding alone), `test_compiler.py` `ConstructorTests`, `test_source_eval.py` |
| 4. Nested lets and lambdas, let-initializer scope, both fix binders, coincident binders, open terms, encoding-name collisions, FV preservation, immutability | `test_compiler.py` `ScopeTests`, `NameCollisionTests`, `StructuralTests`; `test_properties.py` (500 seeded random programs) |
| 5. Unselected divergence skipped; strict positions (argument, `let` initializer, pair components) exhaust | `test_compiler.py` `DivergenceTests`, `test_source_eval.py` `StrategyTests` |
| 6. All demonstrations, nested pairs, rejection even in unselected branches | `test_compiler.py` `DemoTests`, `RejectionTests`; `test_properties.py` `DemoStructureTests` |
| 7. Output uses only `Var`/`Lam`/`App`; combinators closed; compilation never calls the evaluator | `test_compiler.py` `StructuralTests`, `test_church.py` `StructureTests`, `test_modules.py` |
| Observers: renamed and computed values, malformed outputs, observation exhaustion, zero under both kinds | `test_church.py` `ObserverTests` |
| Shared evaluator source path; target path uses no source operations | `test_source_eval.py` |

`test_properties.py` compares the compiled results of 250 closed random
programs with the source evaluator. Its names come from a small pool that
overlaps with the encoding and thunk binders. As a check that this suite can
fail, I planted three scope bugs in the compiler: a thunk parameter that is
not fresh, swapped `fix` binders, and a `let` initializer compiled inside its
own scope. The suite caught all three.

## Limitations

- Execution and decoding work on closed programs only. The evaluator raises
  `OpenTermError` for an open program. Compilation and substitution do
  support open terms.
- There is no type checker. Ill-typed programs compile, and the result of
  running them is meaningless. On the source side such programs raise
  `SourceError` when evaluation reaches the bad operation.
- The evaluator reports source-side errors lazily, only when evaluation
  reaches them. Static rejection of unsupported forms is the compiler's job.
- Church numerals are unary, so arithmetic is slow: `SUB m n` costs O(n·m)
  steps, and comparisons are built from `SUB`. Larger inputs need larger
  budgets.
- Substitution, printing and alpha-equivalence are recursive, so a term
  nested more deeply than Python's recursion limit (about 1,000 levels)
  raises `RecursionError`. The reducer itself runs in a loop and has no such
  limit.
- The observers recognize valid encodings but cannot reject every invalid
  untyped term. For example, `lam x. x` is the eta-reduced numeral one and
  decodes as `1`.

## Extensions (optional, not part of the graded core)

Everything under `MySolution/extensions/` is optional. It depends on the
core, and the core never depends on it. It is tested separately and exists
to make the presentation easier.

| Extension | What it does |
| --- | --- |
| `source_parser.py` | A parser for the pretty printer's notation, so `parse(d0exp_pretty(e)) == e`. Keywords cannot be used as variable names, and `(-1 e)` reads as the unary operator `-1`. Both limits come from the printer producing identical text for two different ASTs. |
| `term_parser.py` | The inverse of `term_print`, used by the web front-end |
| `web/` | My Assignment 4 web front-end, adapted. Lint, Interpret (shared evaluator, stoppable), Compile (shows the pure term) and Execute (choose the result kind and both budgets). Input can be pretty-printed or `D0E…` constructor syntax. Canned examples: factorial, Fibonacci, short-circuit, nested pair, LOOP. |

## Attribution

- `lambda1_vp.py` is the supplied course file, copied unchanged.
- `source_visitors.py` is copied from my Assignment 5 solution. The
  substitution and De Bruijn algorithms in `target.py` are ported from it.
- `extensions/web/` is adapted from my Assignment 4 solution.
- Encoding references: A. Church, *The Calculi of Lambda-Conversion* (1941);
  B. C. Pierce, *Types and Programming Languages* (2002), §5.2 (Church
  booleans, numerals, pairs, the pair-based predecessor, and the
  call-by-value fixed-point combinator).
- AI assistance is described in `AI-TRANSCRIPT.md`.
- Completed individually.
