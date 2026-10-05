# Testing

## How to run

```sh
.venv/bin/pytest          # Python tests (tests/py)
node --test               # JavaScript tests (finds tests/js/*.test.js), Node >= 18
```

Latest results (Python 3.12.14, Node.js 22.23.3): pytest **101 passed**;
node:test **34 passed**.

## Automated tests

| File | What it covers |
| --- | --- |
| `tests/py/test_fvset.py` | `d0exp_fvset` for every constructor; the return type is `frozenset`; repeated variables counted once; nested bindings and shadowing; lambda and fix binding; let initializer scope; both branches of `D0Eif0`; unused bindings are not errors. |
| `tests/py/test_reader.py` | Restricted reader: keyword arguments, negative numbers, comments, multi-line and indented input. Rejects empty, whitespace-only and comment-only input, syntax errors, unknown constructors, Python code (`__import__`, `print`), wrong literal types, missing, extra or duplicate arguments, `*args`, unknown operators, and input over the 1 MB UTF-8 limit. Error line numbers are correct. |
| `tests/py/test_tools.py` | **Real** Lint: a closed program passes; an open program lists its names in sorted order; let scope; Lint does not evaluate (`d0exp_evaluate` is patched to fail, and `div_zero` still passes). **Real** Interpret: arithmetic, comparisons, pairs, let, factorial (0, 1, 5, 10) and Fibonacci (0, 1, 2, 15), including base cases; malformed input is an `input` error; `ZeroDivisionError` and `TypeError` are `runtime` errors after Lint passed; `D0V000()` directly and inside a pair is an error. The child-process runner: revision is echoed back, deep recursion (`fact(3000)`), Stop on an infinite loop followed by a successful retry, an early cancel, an abandoned run stopped by the next run, a crashed child reported as a backend failure. Placeholders are never `ok`; Execute without an artifact, or with a stale one, is refused. |
| `tests/py/test_api.py` | HTTP dispatch: each endpoint calls the matching `LanguageTools` method with the given source and revision. Placeholders are never successes. Execute is unavailable. Malformed requests return 400 with failure results and never reach the tools. A tool exception returns 500 with a `backend` failure. The cancel endpoint works, and the page is served. |
| `tests/js/model.test.js` | **Model test with no browser or server.** Initial state, subscribe and notify, manual input without upload, revisions clearing results, empty and over-limit rejection keeping the applied source and the rejected draft, unapplied edits blocking tools and source replacement, discard, the busy state blocking everything, retry after failure or cancel, Clear results (keeps the source, drops the retry offer, a result arriving after clearing is still shown), stale results ignored, Execute unavailable without an artifact, and a future artifact being invalidated when the source changes. |
| `tests/js/controller.test.js` | **Controller test with a substituted backend** (`FakeBackend`); no view code involved. Dispatch to each operation, placeholders, Execute never dispatched, guards on unapplied edits, busy state and conflicting actions, injected backend exception → failure → retry, failure results, Stop sending the run id, upload of valid, invalid-UTF-8, oversized and empty files, upload refused while edits are unapplied. |
| `tests/js/backend.test.js` | `HttpBackend` with a fake `fetch`: request shape, non-JSON HTTP errors and network errors become failure results, cancel aborts a request that never gets answered. |
| `tests/js/examples.test.js` | The canned examples match `samples/factorial.txt` and `samples/fibonacci.txt`. |

Mocks and fakes (`FakeBackend`, `RecordingTools`, fake `fetch`) are used only
to test dispatch and to inject failures. Lint and Interpret are always
tested against the real `lambda1.py`.

## Required test areas → tests

| Assignment test area | Where |
| --- | --- |
| 1. Free variables: all constructors, duplicates, nesting, recursion, let scope, `frozenset` | `test_fvset.py` |
| 2. Lint success and error with names; Lint does not evaluate division by zero | `test_tools.py::test_lint_*`, `test_api.py::test_lint_reports_undeclared_variable` |
| 3. Interpret arithmetic, factorial and Fibonacci including base cases; malformed input; runtime failures | `test_tools.py::test_interpret_*`, `test_error_sentinel_*` |
| 4. Manual input, replacement, editing, rejection keeping the applied source | `model.test.js`, `controller.test.js` (upload tests) |
| 5. Dispatch; placeholders not successes; Execute unavailable | `test_api.py`, `controller.test.js`, `model.test.js` |
| 6. Busy state, backend failure or stop, retry | `model.test.js`, `controller.test.js`, `test_tools.py::test_runner_cancel_*` |

## Requirements F1–F10 → checks

| ID | Automated | Browser (below) |
| --- | --- | --- |
| F1 Load source menu, name and revision | `controller.test.js` (examples, upload), `model.test.js` (manual input) | B1, B2, B3 |
| F2 Edit, Apply, Discard; edits block actions | `model.test.js` (unapplied edits, discard, name kept) | B4 |
| F3 Reject empty, non-UTF-8 and oversized input; keep applied source and draft | `model.test.js`, `controller.test.js`, `test_reader.py` | B5 |
| F4 Five buttons in order; applied source required; Execute disabled | `model.test.js` | B6 |
| F5 Real Lint | `test_fvset.py`, `test_tools.py`, `test_api.py` | B7 |
| F6 Real Interpret; input vs runtime errors | `test_tools.py` | B8 |
| F7 Placeholders and the Execute explanation | `test_tools.py`, `test_api.py`, `controller.test.js` | B9 |
| F8 New revision clears results and artifact; rejection keeps state | `model.test.js` | B4, B5 |
| F9 Action, revision and outcome shown; literal text; Clear results | View uses `textContent` only; `model.test.js`, `controller.test.js` (Clear results) | B10, B13 |
| F10 Busy, Stop, restore, retry, source kept | `controller.test.js`, `model.test.js`, `test_tools.py` | B11, B12 |

## Browser smoke test (manual)

Start the server (`.venv/bin/python -m server`) and open
http://127.0.0.1:5000/. Then fill in the **Observed** column.

Browser: `TODO` · Date: `TODO` · Tester: `TODO`

| # | Steps | Expected | Observed |
| --- | --- | --- | --- |
| B1 | Load the page. Press Tab repeatedly. | Every control can be reached by keyboard and shows a focus outline. The tool buttons are disabled; "No source applied yet."; status "Status: ready." | |
| B2 | Click *Factorial (canned)*. | Editor shows the factorial source. "Applied source: Factorial (canned) — revision 1". The tool buttons except Execute are enabled. | |
| B3 | Choose File → `samples/fibonacci.txt`. | "Applied source: fibonacci.txt — revision 2"; results list cleared. | |
| B4 | Click *Manual input*, type `D0Evar("x")`. Try clicking *Lint* and *Factorial (canned)*. Click *Discard changes*. Click *Manual input* again, type `D0Evar("x")`, then *Apply changes*. | While typing: Lint and the source menu are disabled, with "unapplied changes" shown. Discard brings back the fibonacci source. Apply creates revision 3 named "Manual input". | |
| B5 | Delete all the text (or type only spaces), then *Apply changes*. Then choose a non-UTF-8 file (e.g. any `.png` renamed to `.txt`). | "Error: Changes not applied: The source is empty…"; revision stays 3; the editor still shows the rejected text. The file is rejected with "not valid UTF-8 text"; revision unchanged. | |
| B6 | Look at the action row after restoring a valid program. | Buttons in order: Lint, Interpret, Type-check, Compile, Execute. Execute is disabled, with an explanation under the row. | |
| B7 | With `D0Evar("x")` applied, click *Lint*. Edit it to `D0Elet("x", D0Eint(5), D0Evar("x"))`, apply, and click *Lint*. | "Lint · revision 3 · Error (undeclared variables)" "Undeclared variable(s): x". Then "Lint · revision 4 · Success" "No free variables found." | |
| B8 | *Interpret*. Load `samples/div_zero.txt`, then *Lint* and *Interpret*. Load `samples/malformed.txt` and click *Interpret*. | `D0Vint(arg1=5)`. div_zero: Lint Success, Interpret "Error (runtime)" ZeroDivisionError. malformed: "Error (input)" with "Invalid input: … must be an integer literal". | |
| B9 | Click *Type-check*, then *Compile*. | Both show "Not implemented" with "Type checking is not yet implemented." and "Compilation is not yet implemented." Execute stays disabled. | |
| B10 | Load `samples/html_like.txt`, then click *Lint*. | The editor and result show `<b>bold</b>` and `<script>alert(1)</script>` as literal text: no bold text, no alert. Line breaks in the source are preserved. | |
| B11 | Load `samples/infinite_loop.txt`, click *Interpret*, wait 3 s, then click *Stop*. | While running: "Status: busy — Interpret is running…", all controls except Stop are disabled, and the page stays scrollable and responsive. After Stop: "Stopped" result, controls restored, *Retry Interpret* visible. | |
| B12 | With the program from B11 running, stop the server (Ctrl+C in the terminal) and wait. Restart the server, then click *Retry Interpret* (and *Stop*) or load a canned example and click *Interpret*. | "Backend failure: Could not reach the server…" result, source kept, controls restored. After the restart, Retry works. | |
| B13 | After a few results are shown, click *Clear results*. Then click *Lint*. | The list shows "No results for this revision yet."; *Clear results* becomes disabled; source name, revision and editor are unchanged; any *Retry* button disappears. Lint adds a new result normally. | |
