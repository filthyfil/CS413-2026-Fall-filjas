# Testing

## How to run (from `assigns/08/MySolution/`)

```sh
.venv/bin/python -m unittest discover -s tests -v      # 84 Python tests (~85 s)
QUEENS_SKIP_SLOW=1 .venv/bin/python -m unittest discover -s tests -v   # skips the two 8×8 walks (~17 s)
node --test tests/client/*.test.mjs                    # 19 client tests
.venv/bin/mypy                                         # strict type check
```

## Observed results (2026-11-19, Linux, Python 3.12.14, Node 22.23.3, Flask 3.1)

| Suite | Result |
| --- | --- |
| Python `unittest` (full) | `Ran 84 tests in 84.709s` — **OK** |
| Python with `QUEENS_SKIP_SLOW=1` | `Ran 84 tests in 17.233s` — **OK (skipped=8)** |
| Node `node:test` | `tests 19, pass 19, fail 0` |
| `mypy` (strict, `queens_rpc/` + `tests/`) | `Success: no issues found in 16 source files` |

Solver tests run the real LAMBDA3 implementation (`solver/queens_cps.lam`
through the supplied interpreter). Test doubles are used only for the
expiry clock (`FakeClock`), injected failures (a patched `force`, a broken
solver for the internal-error test), and, in the client tests, the server
(`FakeApi`) and timers (`ManualScheduler`).

The main oracle is `reference_trace(n)` in `tests/_support.py`: an
independent, direct-style Python version of the spec's event model. The
LAMBDA3 trace must match it event for event.

## Requirement → tests

Python test IDs are `module.Class.test_name`; client tests are `file › "name"`.

| # | Requirement | Tests | Observed |
| --- | --- | --- | --- |
| 1 | Safety: same row, both diagonals, safe placement | `test_solver_safety.AttacksPredicateTests.*` (`test_same_column`, `test_diagonal_down_left`, `test_diagonal_down_right`, `test_safe_placements`); `CpsSafetyCheckTests.test_same_column_conflict`, `test_both_diagonal_directions`, `test_safe_placement`, `test_empty_board_is_safe`, `test_one_queen_per_row_by_construction`, `test_calls_exactly_one_continuation`, `test_stops_at_first_conflict` | pass. Rows cannot collide (one queen per row by construction); the reference solver's "same row" is our "same column". Stops after **1** `attacks` call on the first conflict. |
| 2 | CPS success/failure paths, resumption at next candidate | `test_cps_search.CpsSearchTests.test_success_receives_board_and_failure_continuation`, `test_failure_when_row_has_no_safe_column`, `test_reject_resumes_at_next_column`, `test_resume_after_solution_continues_search`, `test_backtrack_restores_board_and_tries_next_candidate`, `test_search_is_continuation_driven_not_wrapped` | pass. Marker continuations show the failure continuation is called exactly once, at the end, and that resuming after a solution starts with `backtrack(2,3,[1,3,0])` then `try(3,3)`. |
| 3 | All 8×8 solutions: count 92, deterministic order, no duplicates | `test_solutions_and_events.EightByEightTests.test_exactly_92_solutions`, `test_no_duplicates_and_all_valid`, `test_deterministic_depth_first_order`, `test_full_trace_matches_reference_model`, `test_event_totals`; `SmallBoardTests.test_solution_counts_sizes_1_to_7` | pass. 92 distinct valid boards in lexicographic order, first `0 4 7 5 2 6 1 3`, last `7 3 0 2 5 1 6 4`. Totals: try 15720, place 2056, reject 13664, backtrack 2056, solution 92, done 1 (33,589 events). Sizes 1–7: 1, 0, 0, 2, 10, 4, 40. |
| 4 | Each event kind, correct board snapshot and coordinates | `EventKindTests.test_each_kind_with_coordinates_and_snapshot_4x4`; `EightByEightTests.test_event_schema_and_snapshots`, `test_done_exactly_once_and_last`; `SmallBoardTests.test_full_trace_matches_reference_model_sizes_4_to_6` | pass. A replay checks every event: `try` board = current board with `row = len(board)`; `place` = board + column; `reject` unchanged and really conflicting; `backtrack` removes the last queen; `solution` has length n; `done` exactly once, last, with no other fields. |
| 5 | Laziness: open does no search; forcing a cell doesn't force its tail; bounded prefix leaves later work unforced | `test_laziness.OpeningDoesNoSearchTests.test_open_performs_no_search`, `test_constructing_with_failing_root_continuations_is_harmless`; `ForcingIsBoundedTests.test_forcing_one_cell_does_not_force_its_tail`, `test_bounded_prefix_leaves_later_work_unforced`, `test_each_cell_costs_at_most_one_safety_check`, `test_forced_cells_are_memoized`; `DelayedFailureTests.test_prefix_before_first_solution_never_runs_success_continuation`, `test_unrequested_root_failure_is_never_run`; also `test_rpc_methods.HealthAndOpenTests.test_open_returns_id_and_size_without_forcing` | pass. **Trace hook** (`ApplyCounter` wraps the interpreter's `_d0val_apply`): open on 10×10 = 1 application, 0 `attacks`; first cell = 0 `check_safe`; 32 events on 10×10 < 100 `attacks`; every single cell ≤ 9 `attacks`. **Delayed failures:** continuations that divide by zero are not reached by a 200-event prefix (the first solution is event 1858), only when the stream is read that far. Tails are confirmed unevaluated via the interpreter's `evaluated` flag, not by printing `<lazy>`. |
| 6 | Exhaustion, repeated next, close, unknown ID, cleanup, expiration | `test_streams.StreamTableTests.*` (`test_exhaustion_releases_solver_state_and_repeats_done`, `test_close_and_unknown`, `test_expiry_after_inactivity`, `test_purge_expired_cleans_up`, `test_max_streams_and_sweep_before_limit`, `test_failed_take_does_not_advance`, `test_concurrent_takes_on_one_stream_are_serialized`, `test_ids_are_distinct_uuid4`); `test_rpc_methods.NextTests.test_exhaustion_then_repeated_next`; `LifecycleTests.*` | pass. After `done` the cursor is `None` and `next` keeps returning `[]`/`true`; closed/unknown/expired IDs → −32001; table size drops to 0 after close or expiry (fake clock, TTL 60 s); a mid-batch failure leaves the stream unmoved; 4 threads × 10 takes yield exactly the trace prefix. |
| 7 | JSON-RPC IDs, malformed envelopes, unknown methods, invalid params, notifications, application errors | `test_envelope.RequestIdTests.*`, `MalformedEnvelopeTests.*`, `NotificationTests.*`, `InternalErrorTests.*`, `TransportTests.*`, `BatchTests.*`; `test_rpc_methods.HealthAndOpenTests.test_invalid_sizes`, `test_validation_happens_before_allocation`, `test_unexpected_params_rejected`; `NextTests.test_invalid_limits`, `test_invalid_stream_id_params`; `LifecycleTests.test_too_many_streams` | pass. IDs echoed with their type (int, str, float, null); 11 malformed envelopes → −32600 with id null; parse errors → −32700; notifications → HTTP 204, empty body, even when they fail; crash → −32603 with no details; no response contains `Traceback`, paths, `D0V`, `<lazy>`; 415 / 405 / 404 / 413 at the transport level. |
| 8 | `queens.next` limits 1 and 32; never more than requested | `test_rpc_methods.NextTests.test_limit_1_and_32`, `test_never_more_than_requested`, `test_limit_defaults_to_1`, `test_invalid_limits`; `test_http_e2e…test_open_through_92_solutions_to_done` | pass. Limit 1 → exactly 1 event, limit 32 → exactly 32; 0, 33, 1.5, "1", `true` → −32602 and consume nothing. |
| 9 | HTTP client flow: open → all 92 solutions → completion | `test_http_e2e.HttpEndToEndTests.test_open_through_92_solutions_to_done`, `test_small_flow_and_static_client` | pass. A real socket server + `urllib`: 1050 calls of limit 32 (= ⌈33589/32⌉), the 92 solutions equal the reference list, `done` once, then `[]`/`true`, close, then −32001. The page and all static assets are served; traversal → 404. |
| 10 | Browser controls: start/reset, step, play/pause, next solution, RPC failure handling | **Automated:** `player.test.mjs` › "start opens a stream and fetches nothing", "step shows exactly one event per click and fetches in small batches", "play advances one event per timer tick and pause stops it", "next solution runs to the first solution, then the next one", "whole 8x8 flow: 92 solutions, done once, stream closed, then restartable", "reset closes the stream and ignores a response still in flight", "controls are ignored in states where they do not apply", "network failure shows an error, and retry continues on the same stream", "failure during playback stops the timer", "an expired stream is not resumable; retry opens a new stream", "opening failure is reported and retry reopens"; `rpc.test.mjs` › all 5; `events.test.mjs` › all 3. **Manual:** checklist below. | Automated: 19/19 pass. Manual: M1–M15 all pass (below). |

## Manual browser checklist (requirement 10)

Start the server with `.venv/bin/python -m queens_rpc` and open
<http://127.0.0.1:8000/>.

Performed by the student in a browser on 2026-11-19. All items passed
("it all works well").

| # | Action | Expected | Result |
| --- | --- | --- | --- |
| M1 | Load the page | 8×8 board with row/column labels 0–7, status "Press Start, Step, or Play to begin", Step/Play/Next enabled, Reset disabled, counters 0 | ☑ pass |
| M2 | Click **Start** | Badge "Paused", log "Opened 8×8 stream", **RPC calls 1, Fetched 0** (no search yet) | ☑ pass |
| M3 | Click **Step** 4× (or press `→`) | One event per click: yellow outline (try) → green pop (place) → try in row 1 → red ✕ with the row-0 queen outlined (reject); the status names the attacker; Fetched grows in steps of 4 | ☑ pass |
| M4 | Click **Play**, then change **Speed** | Events animate continuously; the label shows ms/event and the speed changes live; the button reads "Pause" | ☑ pass |
| M5 | Click **Pause** (or `Space`) | Animation stops on the current event; Step works again | ☑ pass |
| M6 | Watch a backtrack | Purple dashed queen fades out, the board is restored, and the next try is one column right | ☑ pass |
| M7 | Click **Next solution** (`N`) | Fast-forwards; stops with a gold glow on `0 4 7 5 2 6 1 3`; Solutions = 1; the log shows "Fast-forwarded through … events" then the solution | ☑ pass |
| M8 | Click **Next solution** again | Stops on `0 5 7 2 6 3 1 4`; Solutions = 2 | ☑ pass |
| M9 | Choose 4×4, then Next solution ×3 | Board resizes and resets; solutions `[1,3,0,2]`, `[2,0,3,1]`, then the board dims with the banner "Search complete: 2 solutions found…", distinct from a solution; Step/Play/Next disabled | ☑ pass |
| M10 | Click **Restart search** in the banner | Fresh stream, counters reset, search can run again | ☑ pass |
| M11 | Mid-search, click **Reset** (`R`) | Board and log cleared, badge "Not started"; the old stream is closed on the server | ☑ pass |
| M12 | Start a search, stop the server (Ctrl-C), click **Step** | Red banner "Network error: cannot reach the server. Is the server still running?" with **Retry** and **Restart search**; badge "Error" | ☑ pass |
| M13 | Restart the server, click **Retry**, then **Step** | Retry returns to Paused (a network error is retryable). The next Step finds that the restarted server has no record of the stream, so the banner says so and offers only **Restart search**, which works | ☑ pass |
| M14 | Try 10×10 and click Step / Next solution | Board shows 10 columns; events arrive immediately (no long wait), showing the stream is lazy on a large board | ☑ pass |
| M15 | Narrow the window to phone width | Panel moves under the board; no horizontal scrolling | ☑ pass |
