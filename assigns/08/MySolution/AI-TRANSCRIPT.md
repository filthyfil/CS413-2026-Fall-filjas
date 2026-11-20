# AI Transcript

> **Sections marked ✍️ STUDENT are for the student to complete.** Everything
> else was drafted by the AI assistant and records what it did. Please check
> it against your own memory of the session and correct anything inaccurate.

## AI tools used

| Tool | Model | Used for |
| --- | --- | --- |
| Claude Code (CLI agent, working directly in this repository) | Claude Opus 5.5 | Explaining the assignment; writing the LAMBDA3 solver, Python service, browser client, tests, and README; running tests and mypy |

AI **was** used for this assignment, extensively.

## Prompts and what the AI did

The prompts below are the student's messages, in order, quoted as typed.

1. **"ok"** (after opening `Assign08.md`)
   The AI read the spec and summarized it: architecture diagram, event
   table, RPC methods, grading weights, and a suggested build order. It
   noted that `MySolution/` was empty and the assignment was due that day.

2. **"ok let's write the CPS solver"**
   The AI read `lambda3.py` (parser, type checker, evaluator) and the
   reference `eight_queens*.lam` files, and noted the language's limits: no
   strings, records, or variants; `fix` binds a single name. It then wrote
   `solver/queens_cps.lam`:
   - events as `(kind, column, row, board)` integer-coded tuples;
   - boards stored newest-row-first;
   - a polymorphic CPS `check_safe[R]`;
   - `try_column` with a local `search`, to work around the lack of mutual recursion;
   - `emit`, which puts each continuation call behind a fresh suspension.

   It verified the solver with scratch scripts:
   - solution counts for sizes 1–8 (1, 0, 0, 2, 10, 4, 40, 92), no duplicates;
   - `place` and `backtrack` counts equal; `done` once and last;
   - bounded Python stack depth on 10×10.

   Along the way it found that `python3` on this machine is 3.10 and that
   `lambda3.py` needs `python3.12`.

3. **"ok now the python adapter"**
   The AI first wrote a standard-library-only design. The student
   interrupted:

4. **"use flash and take inspiration from assign/07"** (Flask)
   The AI read the Assign07 solution and rebuilt the adapter in the same
   shape:
   - `jsonrpc.py` copied from Assign07 with only doc changes;
   - new `solver.py` (LAMBDA3 bridge), `streams.py` (UUID stream table with
     per-stream locks, inactivity TTL, sweep-on-access), `service.py` (four
     methods + validation), `app.py` (Flask), `__main__.py`;
   - requirements files, `mypy.ini`, and a `.venv`.

   It exercised the contract through Flask's test client, including the
   full 8×8 run over HTTP (92 solutions).

5. **"ok now the browser client"**
   The AI wrote `client/`:
   - `rpc.js`: transport with typed errors;
   - `events.js`: pure conflict and description helpers;
   - `player.js`: playback state machine that fetches small batches only when its buffer is empty;
   - `board.js`: renderer;
   - `main.js`, `index.html`, `app.css`.

   It drove the real `player.js`/`rpc.js` from Node against the live
   server: step, play, next solution, full run to `done`, network failure
   and retry, expired stream, reset. It did **not** visually inspect the
   page in a browser.

6. **"ok now the tests"** and **"and run the type checker mypy"**
   The AI wrote the Python `unittest` suite (`tests/`) and the Node
   `node:test` suite (`tests/client/`). This included:
   - an independent direct-style reference model of the event trace;
   - a trace hook that counts interpreter applications, used to prove laziness;
   - delayed divide-by-zero continuations that would fail if forced.

   It fixed three bugs **in its own tests** that the first runs exposed: a
   board it wrongly claimed was safe; a guessed first-solution index (876
   instead of 1858); a fake `fetch` returning the wrong result. It extended
   `mypy.ini` to cover `tests/` and fixed the 9 mypy errors that produced,
   in the test code and the config, without `type: ignore` except one
   deliberate subclass stub. mypy strict now reports no issues in 16 files.

7. **"Create README; and leave human sections for me to complete in AI transcript please"**
   The AI wrote `README.md` and this file, leaving the sections below for the student.
   On the final full rerun it found that its own mypy-driven edit to
   `tests/_support.py` had broken every test module's imports. An earlier
   run looked green only because the pipeline ended in `grep`, which hid
   the failing exit code. It fixed the import order and reran the suites
   without the pipe: 84 Python tests OK, 19 Node tests OK, mypy clean.

8. **"Yeah the page in the browser looks good; please write the design and necessary documents"**
   The AI wrote `DESIGN.md` (architecture diagram, board invariant,
   continuation signatures and pseudocode, how the CPS search becomes a
   lazy stream with the work per forced cell, event schema, one example
   exchange per method, lifetime/limits/errors) and `TESTING.md`
   (requirement → test mapping with observed results, plus a manual
   browser checklist). DESIGN.md says openly that it was written up after
   the code, although the spec asks for it first.

## How the AI checked its own work

- Solver output was compared against known N-Queens counts, and the whole
  event trace for sizes 4, 5, 6 and 8 against an independent Python
  reference written directly from the spec's prose.
- Laziness was checked by counting work, not by inspecting `<lazy>` strings:
  - opening a stream performs exactly one application and zero safety checks;
  - one forced cell runs at most one `check_safe`;
  - unrequested continuations that divide by zero are never reached.
- The RPC contract was checked through Flask's test client and through a
  real socket server with `urllib`.
- Type checking: `mypy --strict` over `queens_rpc/` and `tests/`.
- Final results are recorded in TESTING.md.

## ✍️ STUDENT: How I reviewed the AI's work

I read the code, and tried to understand and ensure laziness and that CPS is really happening and not faked.

Finally, confirm against the real solution since soln order is deterministic, and should be the same.

## ✍️ STUDENT: Manual browser testing

I reviewed the animation elements by looking to make sure it looks good.

## ✍️ STUDENT: AI suggestions I rejected or questioned

AI wanted to write the http server manually, I said to try again using flask, and to reuse assign07 as needed.

## ✍️ STUDENT: What I understand and could explain without the AI

I asked AI to create the eight queens solution using CPS. Honestly, the implementation is very hard to follow (that is, CPS style) compared to a python implementation.

I think CPS and lazy evaluation complement each other very well. You compute what you want, and leave a continuation for further work, if necessary. For iterative problem solver, I think this is a good way to approach the problem, to remain lazy, and complete as little repetitive work as possible.
