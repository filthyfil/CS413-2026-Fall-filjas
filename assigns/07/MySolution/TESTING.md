# Testing

## How the tests work

The tests are **HTTP-level tests run in-process**. Flask's test client sends
real HTTP requests (method, headers, body bytes) through the full stack:
Flask, then the JSON-RPC dispatcher, then the service layer, then LAMBDA3. No
network socket or running server is needed.

Every response is checked at two layers:

- **Transport:** HTTP status (200 / 204 / 404 / 405 / 413 / 415) and
  `Content-Type`.
- **JSON-RPC:** the body is validated against [`rpc.schema.json`](./rpc.schema.json).
  The checks cover:
  - exactly one of `result` / `error`;
  - an integer `code` and a string `message`;
  - an allowed result shape;
  - the request `id` echoed with the same JSON type (`7` must not come back
    as `"7"`).

  Every error response is also scanned for leaked internals: `Traceback`,
  `File "`, `/home/`, `.py`, `lambda3`, `D0V`, `ENVcns`, `object at 0x`.

**Test doubles** appear only in `test_failures.py`, and only for failure
behavior and the service/worker dispatch boundary. Every successful
type-check, interpretation, and compilation test calls the real LAMBDA3.

```sh
# from assigns/07/
MySolution/.venv/bin/python -m unittest discover -s MySolution/tests -v   # our suite
python3 -m unittest discover -s TEST -v                                   # provided suite (server running)
# from assigns/07/MySolution/
.venv/bin/mypy                                                            # static types
```

| File | Tests | Focus |
| --- | --- | --- |
| `tests/_support.py` | – | Test client, schema validators, leak check, shared programs |
| `tests/test_lambda_methods.py` | 27 | Health; type-check / interpret / compile on real LAMBDA3; function values; syntax and type errors |
| `tests/test_envelope.py` | 29 | Parse errors, invalid requests, unknown methods, every params rule, HTTP transport |
| `tests/test_batches.py` | 12 | Batches, notifications, ID matching |
| `tests/test_failures.py` | 19 | Injected crashes, injected timeout, real deadline, runtime errors, stack limit |
| `tests/test_contract_docs.py` | 6 | The schema is valid; every RPC.md request/response example replays exactly |

---

## Required behaviors → tests

Test names are `module.Class.test_method`. All are in `MySolution/tests/`.

### 1. `service.health` returns status and API version and preserves the id

| Test | Checks |
| --- | --- |
| `test_lambda_methods.HealthTests.test_health_returns_status_version_and_preserves_string_id` | Exact result `{"status":"ok","version":"1.0"}`, id `"health-1"` |
| `test_lambda_methods.HealthTests.test_health_preserves_numeric_and_null_ids` | Ids `0`, `7`, `-3`, `2.5`, `null` returned with the same type |
| `test_lambda_methods.HealthTests.test_health_accepts_omitted_params` | `params` may be omitted for health |

### 2. Type-checking valid programs returns the formatted type

| Test | Checks |
| --- | --- |
| `test_lambda_methods.TypecheckTests.test_valid_programs_return_formatted_type` | `sint`, `bool`, `(sint, bool)`, nested tuples, `sint -> sint`, `List[sint]`, `Optn[sint]`, factorial |
| `test_lambda_methods.TypecheckTests.test_typecheck_does_not_evaluate` | Programs that would fail at run time still type-check |
| `test_lambda_methods.TypecheckTests.test_typecheck_with_library` | `list_range(1, 4)` with `libraries: ["list"]` is `List[sint]` |

### 3. Interpretation: arithmetic, factorial, a tuple, and a collection

| Test | Checks |
| --- | --- |
| `test_lambda_methods.InterpretTests.test_arithmetic` | `20 + 22` → `42`; precedence; `if` |
| `test_lambda_methods.InterpretTests.test_factorial` | `fact(6)` → `720`, `fact(10)` → `3628800` |
| `test_lambda_methods.InterpretTests.test_tuple` | `(1, true)` → type `(sint, bool)`, value `(1, true)`; projection |
| `test_lambda_methods.InterpretTests.test_collections` | `List[sint]` `[1, 2]`, `List[bool]` `[true]`, `Optn[sint]` `optn_cons(5)` |
| `test_lambda_methods.InterpretTests.test_collection_from_library` | `list_map(list_range(1, 4), …)` → `[1, 4, 9]` |
| `test_lambda_methods.InterpretTests.test_all_libraries_load_together` | All four `mylib` modules load in one program |
| `test_lambda_methods.InterpretTests.test_print_output_is_not_part_of_result` | `print(5)` → `unit` / `()` |

### 4. Python and JavaScript compilation return nonempty code and the right target

| Test | Checks |
| --- | --- |
| `test_lambda_methods.CompileTests.test_python_target_returns_parseable_python` | `target: "python"`, nonempty code, `ast.parse` succeeds (parsed only, never executed) |
| `test_lambda_methods.CompileTests.test_javascript_target_returns_javascript` | `target: "javascript"`, JS markers present, no Python markers |
| `test_lambda_methods.CompileTests.test_factorial_compiles_for_both_targets` | Both targets, outputs differ |
| `test_lambda_methods.CompileTests.test_generated_code_matches_lambda3_unchanged` | The returned code is byte-identical to `d0exp_compile` / `d0exp_compile_js` |
| `test_lambda_methods.CompileTests.test_compile_does_not_run_the_program` | A program that fails at run time compiles fine |
| `test_lambda_methods.CompileTests.test_compile_with_library` | Compiling with `libraries` |

### 5. Syntax errors and type errors have distinct documented codes

| Test | Checks |
| --- | --- |
| `test_lambda_methods.LanguageErrorTests.test_syntax_error_has_position_details` | `-32010`, data `{detail, line: 1, column: 4, text}` |
| `test_lambda_methods.LanguageErrorTests.test_syntax_error_on_later_line` | Line/column on line 2 |
| `test_lambda_methods.LanguageErrorTests.test_type_error` | `-32011`, detail `+: expected bool, got sint` |
| `test_lambda_methods.LanguageErrorTests.test_syntax_and_type_codes_differ` | The two codes differ |
| `test_lambda_methods.LanguageErrorTests.test_every_source_method_checks_before_running` | interpret and both compile targets reject syntax, type, and unbound errors first |
| `test_lambda_methods.LanguageErrorTests.test_lambda_syntax_error_is_not_a_json_parse_error` | Source text that looks like broken JSON is `-32010`, not `-32700` |

### 6. Malformed JSON, invalid envelopes, unknown methods, bad params, blank and oversized source

| Test | Checks |
| --- | --- |
| `test_envelope.ParseErrorTests.test_malformed_json` | Five malformed bodies → `-32700`, `id: null` |
| `test_envelope.ParseErrorTests.test_non_standard_json_constants` | `NaN` → `-32700` |
| `test_envelope.ParseErrorTests.test_invalid_utf8` | `-32700`, `reason: invalid_utf8` |
| `test_envelope.InvalidRequestTests.test_non_object_requests` | `42`, `"…"`, `null`, `true` → `-32600` |
| `test_envelope.InvalidRequestTests.test_bad_jsonrpc_version` | `"1.0"`, `2.0`, `null`, missing |
| `test_envelope.InvalidRequestTests.test_bad_method` | Missing / non-string method |
| `test_envelope.InvalidRequestTests.test_bad_id_types_get_null_id` | Bool / object / array ids → `-32600` with `id: null` |
| `test_envelope.InvalidRequestTests.test_non_structured_params` | String / number / bool / null params → `-32600` |
| `test_envelope.InvalidRequestTests.test_unexpected_member` | Extra top-level member |
| `test_envelope.InvalidRequestTests.test_invalid_request_without_id_still_gets_a_response` | Invalid request lacking an id is answered with `id: null` |
| `test_envelope.MethodNotFoundTests.test_unknown_method` | `-32601`, `data.method` |
| `test_envelope.MethodNotFoundTests.test_method_names_are_case_sensitive` | `Service.Health` etc. → `-32601` |
| `test_envelope.InvalidParamsTests.test_absent_params_for_source_methods` | Absent or `{}` params → `-32602` `missing` |
| `test_envelope.InvalidParamsTests.test_array_params_are_rejected` | Array params → `-32602` |
| `test_envelope.InvalidParamsTests.test_wrongly_typed_source` | `12`, `null`, list, object, bool |
| `test_envelope.InvalidParamsTests.test_blank_source` | `""`, spaces, whitespace-only |
| `test_envelope.InvalidParamsTests.test_oversized_source` | Exactly 65 536 bytes accepted; 65 537 → `too_large` with byte counts |
| `test_envelope.InvalidParamsTests.test_source_limit_counts_utf8_bytes_not_characters` | Multi-byte characters counted as bytes |
| `test_envelope.InvalidParamsTests.test_unknown_param_names` | Unknown params rejected |
| `test_envelope.InvalidParamsTests.test_compile_target` | Missing / wrong type / `ruby` / `Python` / `js` |
| `test_envelope.InvalidParamsTests.test_libraries` | Wrong type, unknown (including `../etc/passwd`), duplicate |
| `test_envelope.InvalidParamsTests.test_params_checked_before_source_is_parsed` | Bad target reported before the syntax error |
| `test_envelope.TransportTests.*` (7 tests) | `charset` accepted; 415 for wrong or missing media type; 405 for GET/PUT/DELETE; 404 for resource-style URLs; 413 over 2 MiB; RPC errors are HTTP 200 |

### 7. A function result is formatted without leaking closure internals

| Test | Checks |
| --- | --- |
| `test_lambda_methods.FunctionValueTests.test_function_values_use_d0val_format` | `<lam>`, `<fix>`, `(1, <lam>)`, with types; no `env`, `D0V`, `closure`, `object at` |

### 8. Injected backend failure or timeout returns the documented error, keeps the id, and shows no traceback

| Test | Checks |
| --- | --- |
| `test_failures.InjectedBackendFailureTests.test_type_checker_crash` | `RuntimeError` with a fake secret path injected into the front end. All three source methods return exactly `{"code": -32603, "message": "Internal error"}` with the id. The secret is absent from the response but present, with a traceback, in the server log. |
| `test_failures.InjectedBackendFailureTests.test_compiler_crash` | Same, injected into `d0exp_compile_js` |
| `test_failures.InjectedBackendFailureTests.test_interpreter_worker_crash` | The worker reports `InternalFailure`, giving `-32603` |
| `test_failures.InjectedBackendFailureTests.test_failing_notification_is_still_silent` | A crash in a notification still gives 204 |
| `test_failures.InjectedBackendFailureTests.test_crash_in_batch_only_affects_its_member` | The other batch member succeeds |
| `test_failures.InjectedBackendFailureTests.test_compile_stack_overflow_reports_compile_stage` | Injected `RecursionError` in the compiler → `-32014`, `stage: compile` |
| `test_failures.InjectedTimeoutTests.test_timeout_outcome_maps_to_32012_and_preserves_id` | Injected interpreter times out → exact `-32012` error with `timeoutSeconds` |
| `test_failures.InjectedTimeoutTests.test_worker_receives_source_libraries_and_deadline` | The boundary passes source, libraries, and deadline |
| `test_failures.InjectedTimeoutTests.test_worker_is_not_started_for_invalid_programs` | No worker for syntax, type, or param errors |
| `test_failures.InjectedTimeoutTests.test_only_interpret_uses_the_worker` | Typecheck and compile never start a worker |
| `test_failures.InjectedTimeoutTests.test_timeout_in_batch_only_affects_its_member` | The other batch member succeeds |
| `test_failures.RealDeadlineTests.test_slow_program_times_out_and_worker_is_terminated` | **Real** worker, 0.5 s deadline, `fib(30)` → `-32012` in 0.5–3 s; no child processes remain |
| `test_failures.RealDeadlineTests.test_service_keeps_working_after_a_timeout` | The next request succeeds |
| `test_failures.RealDeadlineTests.test_typecheck_and_compile_of_slow_program_are_fast` | Typecheck and compile of `fib(30)` finish in under 0.5 s |
| `test_failures.RuntimeErrorTests.test_well_typed_programs_failing_at_run_time` | `list_head`/`list_tail`/`optn_get` on empty values, division by zero → `-32013` |
| `test_failures.StackLimitTests.test_evaluation_stage` | `sum(50)` works; `sum(1000)` → `-32014` `evaluate` |
| `test_failures.StackLimitTests.test_parse_stage` | 300 nested parentheses → `-32014` `parse`, for all three methods |
| `test_failures.StackLimitTests.test_typecheck_stage` | `1 + 1 + …` (1500 terms) → `-32014` `typecheck` |
| `test_failures.StackLimitTests.test_stack_errors_are_deterministic_and_not_fatal` | Same result twice; the service still works |

### 9. LAMBDA3 type-checking rejects an unbound variable

| Test | Checks |
| --- | --- |
| `test_lambda_methods.LanguageErrorTests.test_unbound_variable_rejected_by_type_checker` | `x + 1` → `-32011`, detail `unbound variable 'x'`, for typecheck and interpret |
| `test_lambda_methods.LanguageErrorTests.test_every_source_method_checks_before_running` | `y` rejected by interpret and both compile targets |

### 10. Batches and notifications

| Test | Checks |
| --- | --- |
| `test_batches.BatchTests.test_mixed_batch_preserves_ids_and_omits_notifications` | 5 members (3 calls, 2 notifications, one of which fails) → 3 responses matched by id |
| `test_batches.BatchTests.test_each_member_matches_its_own_id` | Each response's value matches its own request |
| `test_batches.BatchTests.test_invalid_members_get_null_id_errors` | Non-objects, bad id, and invalid-without-id → `-32600` with `id: null` |
| `test_batches.BatchTests.test_member_errors_do_not_affect_other_members` | `-32601`, `-32602`, `-32010`, and a success in one batch |
| `test_batches.BatchTests.test_duplicate_ids_are_answered_individually` | Both answered |
| `test_batches.BatchTests.test_notification_only_batch_returns_204_empty_body` | 204, empty body (including a failing notification) |
| `test_batches.BatchTests.test_empty_batch_is_one_invalid_request_object` | `[]` → one object (not an array), `-32600`, `id: null` |
| `test_batches.BatchTests.test_oversized_batch_is_rejected_as_a_whole` | 26 members → one `-32600`; 25 members all answered |
| `test_batches.BatchTests.test_nested_batch_member_is_invalid` | `[[…]]` → `-32600` |
| `test_batches.NotificationTests.test_single_notification_returns_204_empty_body` | 204, empty body |
| `test_batches.NotificationTests.test_failing_notifications_are_silent` | Syntax error, blank source, array params, unknown method → 204 |
| `test_batches.NotificationTests.test_null_id_is_a_call_not_a_notification` | `"id": null` gets a response |

### Contract and documentation

| Test | Checks |
| --- | --- |
| `test_contract_docs.SchemaTests.*` (3 tests) | The schema itself is valid draft 2020-12, accepts valid requests, rejects invalid ones and responses with both `result` and `error` |
| `test_contract_docs.DocumentedExampleTests.test_documented_responses_match_schema` | Every response example in RPC.md validates |
| `test_contract_docs.DocumentedExampleTests.test_documented_request_response_pairs_replay_exactly` | Every RPC.md request immediately followed by its response is sent to the real service and must match exactly; at least 12 pairs are replayed. Skipped: the abbreviated compile example and the 5-second timeout demo. |

---

## Observed results

Recorded on 2026-11-10, Linux, Python 3.12.14, Flask 3.1.3.

| Check | Command | Result |
| --- | --- | --- |
| Our suite | `MySolution/.venv/bin/python -m unittest discover -s MySolution/tests -v` | **93 tests, OK** (≈ 2.9 s) |
| Provided black-box suite against a live server | `python3 -m unittest discover -s TEST -v` | **15 tests, OK** (≈ 0.34 s) |
| Static types | `.venv/bin/mypy` (strict for `lambda_rpc`) | **Success: no issues found in 13 source files** |

Additional manual checks with `curl` against the live server (outputs are in
[`README.md`](./README.md)):

- Factorial → `720`; `list_range(1, 4)` with `libraries: ["list"]` →
  `[1, 2, 3]`.
- `x + 1` → `-32011` `unbound variable 'x'`.
- `fib(30)` → `-32012` after 5.02 s. Afterwards only the server, the
  forkserver, and the resource tracker were running, so the killed worker
  had not lingered.
- `sum(1000)` → `-32014` `evaluate`; 300 nested parentheses → `-32014`
  `parse`.
- 415 for `text/plain`, 405 for GET, 404 for `/other`, 413 for a 3 MB body.

Problems found while writing the tests. All were mistaken expectations in
the tests; the service needed no changes:

- `list_head(list_nil())` type-checks to `?t1` (an unconstrained type
  variable), not `sint`. The test now uses
  `list_head(list_tail(list_cons(1, list_nil())))`.
- `json.dumps` escapes `…` as `…`, so the "skip abbreviated example"
  check never matched. Fixed with `ensure_ascii=False`.

Problems found by mypy (before strict typing was added):

- The worker's result was a loose `(kind, payload: object)` pair, so the
  service's use of it was unchecked. It was replaced by one dataclass per
  outcome (`Ok`, `SyntaxFailure`, `TypeFailure`, `RuntimeFailure`,
  `StackFailure`, `InternalFailure`, `Timeout`), matched by class.
- An exception variable name was reused across two `except` blocks. Renamed.

---

## Architecture

```
            client (curl, TEST/ suite, Flask test client)
                               │  POST /rpc   Content-Type: application/json
                               ▼
┌───────────────────────────────────────────────────────────────────────┐
│ HTTP transport             lambda_rpc/app.py   (Flask)                 │
│  • POST only (405), JSON media type only (415), body ≤ 2 MiB (413)     │
│  • reply → HTTP 200 + JSON      no reply → HTTP 204                    │
└──────────────────────────────┬────────────────────────────────────────┘
                               │ body bytes            ▲ dict / list / None
                               ▼                       │
┌───────────────────────────────────────────────────────────────────────┐
│ JSON-RPC dispatcher        lambda_rpc/jsonrpc.py   (no Flask, no LAMBDA)│
│  • UTF-8 + JSON parse (-32700)   • envelope checks (-32600)            │
│  • batches, notifications, id echo   • method lookup (-32601)          │
│  • unexpected exception → log traceback, reply -32603                  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │ method(params)        ▲ result / RpcError
                               ▼                       │
┌───────────────────────────────────────────────────────────────────────┐
│ Service adapter            lambda_rpc/service.py                       │
│  • params validation (-32602)                                          │
│  • parse + type-check first; map LambdaSyntaxError → -32010,           │
│    TypeCheckError → -32011, RecursionError → -32014                    │
│  • typecheck / compile in-process; interpret via the worker            │
└───────────────┬───────────────────────────────────┬───────────────────┘
                │                                   │ source, libraries, deadline
                │                                   ▼
                │               ┌───────────────────────────────────────┐
                │               │ Worker            lambda_rpc/worker.py│
                │               │  child process (forkserver); killed at│
                │               │  the deadline → -32012                │
                │               │  returns Ok / RuntimeFailure (-32013) │
                │               │  / StackFailure (-32014) / …          │
                │               └───────────────────┬───────────────────┘
                ▼                                   ▼
┌───────────────────────────────────────────────────────────────────────┐
│ LAMBDA3 front end          lambda_rpc/frontend.py                      │
│  • locates LAMBDA3, loads mylib/*.lam (d0cls_parse + D0Elets)          │
│  • labels stack overflows by stage (parse / typecheck)                 │
└──────────────────────────────┬────────────────────────────────────────┘
                               ▼
┌───────────────────────────────────────────────────────────────────────┐
│ LAMBDA3 (provided, unchanged)   LAMBDA3/lambda3.py, LAMBDA3/mylib/     │
│  d0exp_parse_and_typecheck · d0exp_evaluate · format_type ·            │
│  d0val_format · d0exp_compile · d0exp_compile_js                       │
└───────────────────────────────────────────────────────────────────────┘
```

Dependencies point only downward. `jsonrpc.py` does not import Flask or
LAMBDA3. `service.py` does not know about HTTP or envelopes. Only
`frontend.py` imports `lambda3`.
