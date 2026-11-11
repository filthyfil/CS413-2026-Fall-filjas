# LAMBDA3 JSON-RPC Service (Assignment 7)

A JSON-RPC 2.0 service that makes the LAMBDA3 language tools (parser, type
checker, interpreter, and Python/JavaScript compilers) available over HTTP at
a single endpoint, `POST /rpc`.

- **Contract:** [`RPC.md`](./RPC.md) and the JSON Schema [`rpc.schema.json`](./rpc.schema.json)
- **Tests and architecture:** [`TESTING.md`](./TESTING.md)
- **AI use:** [`AI-TRANSCRIPT.md`](./AI-TRANSCRIPT.md)

| Method | Params | Result |
| --- | --- | --- |
| `service.health` | `{}` | `{"status": "ok", "version": "1.0"}` |
| `lambda.typecheck` | `{"source", "libraries"?}` | `{"type"}` |
| `lambda.interpret` | `{"source", "libraries"?}` | `{"type", "value"}` |
| `lambda.compile` | `{"source", "target": "python" \| "javascript", "libraries"?}` | `{"target", "code"}` |

> **Generated code is returned, never run.** `lambda.compile` returns the
> output of LAMBDA3's `d0exp_compile` / `d0exp_compile_js` unchanged, as a
> string. The service does not execute generated Python or JavaScript, and it
> does not use `exec` or JavaScript evaluation for any method.
> `lambda.interpret` runs the source program only through LAMBDA3's own
> interpreter (`d0exp_evaluate`), in a separate worker process with a
> deadline.

---

## Versions

| Component | Version |
| --- | --- |
| Python | 3.12.14 (3.12 or later required: `lambda3.py` uses `type` statements) |
| Flask | 3.1.3 (Werkzeug 3.1.9) |
| jsonschema | 4.26.0 (tests only) |
| mypy | 2.4.1 (development only) |
| OS used for testing | Linux (worker processes use `forkserver`; other platforms fall back to `spawn`) |

## Layout

```
assigns/07/
├── LAMBDA3/                 provided language implementation (unchanged)
├── TEST/                    provided black-box tests (need a running server)
└── MySolution/
    ├── lambda_rpc/
    │   ├── __main__.py      startup: python -m lambda_rpc
    │   ├── app.py           HTTP transport (Flask): POST /rpc only
    │   ├── jsonrpc.py       JSON-RPC envelopes, IDs, batches, notifications
    │   ├── service.py       the four methods, param validation, error mapping
    │   ├── frontend.py      loads LAMBDA3 + mylib, parse and type-check
    │   └── worker.py        interpretation in a child process with a deadline
    ├── tests/               in-process HTTP tests (Flask test client)
    ├── RPC.md               the RPC contract
    ├── rpc.schema.json      JSON Schema (draft 2020-12) for the envelopes
    ├── requirements.txt     runtime + test dependencies
    ├── requirements-dev.txt adds mypy and type stubs
    └── mypy.ini
```

## Setup

From `assigns/07/MySolution/`. Any Python 3.12+ works in place of
`python3.12`. On this machine the system `python3` is 3.10, which cannot
import `lambda3.py`.

```sh
cd assigns/07/MySolution
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt          # Flask + jsonschema
.venv/bin/pip install -r requirements-dev.txt      # optional: mypy for type-checking
```

With `uv` the equivalent is
`uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt`.

The service finds LAMBDA3 at `../LAMBDA3` relative to `MySolution/`. Set
`LAMBDA3_DIR` to use another copy.

## Running the tests

**Our test suite** (93 in-process HTTP tests; no server needed). Run from `assigns/07/`:

```sh
cd assigns/07
MySolution/.venv/bin/python -m unittest discover -s MySolution/tests -v
```

**The provided black-box suite** (needs the server running, see below). Also from `assigns/07/`:

```sh
python3 -m unittest discover -s TEST -v
```

**Type-checking** (strict mode for the package), from `MySolution/`:

```sh
.venv/bin/mypy
```

See [`TESTING.md`](./TESTING.md) for the mapping from required behaviors to
tests and the observed results.

## Starting the service

```sh
cd assigns/07/MySolution
.venv/bin/python -m lambda_rpc                 # http://127.0.0.1:8000/rpc
.venv/bin/python -m lambda_rpc --port 9000     # another port
LAMBDA_RPC_TIMEOUT=2 .venv/bin/python -m lambda_rpc   # 2 s interpretation deadline
```

**Endpoint:** `POST http://127.0.0.1:8000/rpc` with `Content-Type: application/json`.

This is Flask's development server, intended for local development and tests
only. Stop it with Ctrl-C.

## Limits

| Limit | Value | Error |
| --- | --- | --- |
| Request body | 2 MiB | HTTP 413 |
| `source` | 65 536 bytes (UTF-8) | `-32602` |
| Batch | 25 members | `-32600` |
| Interpretation | 5 s wall clock (`LAMBDA_RPC_TIMEOUT`) | `-32012` |
| Recursion depth | Python's default (inherited from LAMBDA3) | `-32014` |

## HTTP status vs. RPC outcome

**HTTP 200 for every JSON-RPC response object, including errors.**
- A LAMBDA type error, an unknown method, and even malformed JSON
  (`-32700`) or an invalid request (`-32600`) all return HTTP 200. The
  outcome is in the body's `result` or `error`.
- Notifications, and batches made only of notifications, return **HTTP
  204** with an empty body.
- Real transport problems use HTTP codes with a plain-text body: 415 for
  the wrong `Content-Type`, 405 for a method other than POST, 413 for an
  oversized body, and 404 for any path other than `/rpc`.

[`RPC.md`](./RPC.md) §1.1 has the full table.

---

## curl examples

The examples assume the server is running on the default port. The outputs
shown are real responses from this implementation.

### `service.health`

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"service.health","params":{},"id":"health-1"}'
```
```json
{"jsonrpc": "2.0", "result": {"status": "ok", "version": "1.0"}, "id": "health-1"}
```

### `lambda.typecheck`

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.typecheck","params":{"source":"(1, true)"},"id":2}'
```
```json
{"jsonrpc": "2.0", "result": {"type": "(sint, bool)"}, "id": 2}
```

### `lambda.interpret`: factorial

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.interpret","id":3,
       "params":{"source":"let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(6) end"}}'
```
```json
{"jsonrpc": "2.0", "result": {"type": "sint", "value": "720"}, "id": 3}
```

With a standard library module from `LAMBDA3/mylib/`:

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.interpret","params":{"source":"list_range(1, 4)","libraries":["list"]},"id":4}'
```
```json
{"jsonrpc": "2.0", "result": {"type": "List[sint]", "value": "[1, 2, 3]"}, "id": 4}
```

### Unbound variable (type error)

LAMBDA3's type checker rejects the program, so it is never run.

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.interpret","params":{"source":"x + 1"},"id":"unbound"}'
```
```json
{"jsonrpc": "2.0", "error": {"code": -32011, "message": "LAMBDA type error", "data": {"detail": "unbound variable 'x'"}}, "id": "unbound"}
```

A syntax error has its own code, `-32010`, and includes the position:

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.typecheck","params":{"source":"if then"},"id":"syntax"}'
```
```json
{"jsonrpc": "2.0", "error": {"code": -32010, "message": "LAMBDA syntax error", "data": {"detail": "Expected an expression", "line": 1, "column": 4, "text": "if then"}}, "id": "syntax"}
```

### `lambda.compile`

The generated code is long because it starts with LAMBDA3's runtime helpers.
This example prints the target and the code from `_lambda_main` onward:

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.compile","params":{"source":"1 + 2","target":"python"},"id":"py"}' \
  | python3 -c 'import json,sys; r=json.load(sys.stdin)["result"]; c=r["code"]; print(r["target"]); print(c[c.index("def _lambda_main"):])'
```
```text
python
def _lambda_main():
    _v1 = 1
    _v2 = 2
    _v3 = (_v1 + _v2)
    return _v3

_lambda_result = _lambda_main()
```

The same request with `"target":"javascript"` ends with:

```text
function _lambda_main() {
  let _v1 = 1;
  let _v2 = 2;
  let _v3 = (_v1 + _v2);
  return _v3;
}
const _lambda_result = _lambda_main();
```

This code is only returned to the client. The service never runs it.

### Batch with a notification

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d '[
  {"jsonrpc":"2.0","method":"lambda.interpret","params":{"source":"6 * 7"},"id":"answer"},
  {"jsonrpc":"2.0","method":"service.health","params":{}}
]'
```
```json
[{"jsonrpc": "2.0", "result": {"type": "sint", "value": "42"}, "id": "answer"}]
```

### Timeout and stack limit

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.interpret","id":"slow",
       "params":{"source":"let fib : sint -> sint = fix fib(n: sint): sint => if n < 2 then n else fib(n - 1) + fib(n - 2) in fib(30) end"}}'
```
```json
{"jsonrpc": "2.0", "error": {"code": -32012, "message": "Execution timeout", "data": {"timeoutSeconds": 5.0}}, "id": "slow"}
```

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.interpret","id":"deep",
       "params":{"source":"let sum : sint -> sint = fix sum(n: sint): sint => if n <= 0 then 0 else n + sum(n - 1) in sum(1000) end"}}'
```
```json
{"jsonrpc": "2.0", "error": {"code": -32014, "message": "Stack limit exceeded", "data": {"stage": "evaluate", "detail": "Python call stack exhausted"}}, "id": "deep"}
```

A timeout does not prove that a program never terminates. `fib(30)` would
finish, just not within 5 seconds. A stack-limit error reflects a known
limitation of LAMBDA3's recursive implementation, which this service
deliberately does not modify.

### Transport error (not JSON-RPC)

```sh
curl -s -i -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: text/plain' -d '{}' | head -1
```
```text
HTTP/1.1 415 UNSUPPORTED MEDIA TYPE
```
