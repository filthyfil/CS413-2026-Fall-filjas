# LAMBDA3 JSON-RPC Service — RPC Contract

API version: **1.0** · Protocol: **JSON-RPC 2.0** over HTTP/1.1

This document is the contract for the service. It was written before the
dispatcher was implemented; the implementation and the automated tests are
checked against it.

---

## 1. Transport contract

The service exposes exactly **one** HTTP endpoint:

```
POST /rpc
Content-Type: application/json
```

Operations are **not** modeled as resource URLs. Every operation is a JSON-RPC
method named in the request body and sent to the same URL.

| Aspect | Contract |
| --- | --- |
| URL | `http://127.0.0.1:8000/rpc` (default local development address) |
| HTTP method | `POST` only |
| Request media type | `application/json` (a `charset=utf-8` parameter is allowed) |
| Request body | One JSON-RPC request object, or a JSON array of them (a batch), UTF-8 encoded |
| Response media type | `application/json; charset=utf-8` when there is a body |
| Response body | One JSON-RPC response object, an array of them, or **empty** |

### 1.1 HTTP status vs. RPC outcome

This service uses two separate layers, and each reports its own kind of status:

- **HTTP status (transport layer)** says whether the HTTP message was delivered
  to the JSON-RPC processor as a JSON payload. It does **not** say whether the
  method succeeded.
- **JSON-RPC `result` / `error` (application layer)** says what happened when
  the request was processed.

A LAMBDA type error, an unknown method, and even malformed JSON are
*successfully delivered answers*. The transport worked, so they are returned
with **HTTP 200** and a JSON-RPC `error` object.

| Situation | HTTP status | Body |
| --- | --- | --- |
| Any request that produces at least one JSON-RPC response object (success **or** error, including `-32700` parse errors and `-32600` invalid requests) | `200 OK` | JSON-RPC response object or array |
| A single valid notification, or a batch whose members are all valid notifications | `204 No Content` | empty |
| HTTP method other than `POST` on `/rpc` | `405 Method Not Allowed` | not JSON-RPC |
| `Content-Type` missing or not `application/json` | `415 Unsupported Media Type` | not JSON-RPC |
| Request body larger than **2 MiB** | `413 Content Too Large` | not JSON-RPC |
| Any path other than `/rpc` | `404 Not Found` | not JSON-RPC |

Transport errors (405/413/415/404) mean the payload never reached the JSON-RPC
layer, so no JSON-RPC response object is produced. Clients should check the
HTTP status first, then inspect `result` / `error`.

---

## 2. The JSON-RPC envelope

### 2.1 Request object

```json
{"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "1 + 2"}, "id": 1}
```

| Member | Rule |
| --- | --- |
| `jsonrpc` | Required. Exactly the string `"2.0"`. |
| `method` | Required. A string. Method names are **case-sensitive**. |
| `params` | An object for every method in this API. It may be omitted only for `service.health`. |
| `id` | Optional. A string, a number, or `null`. Booleans, objects, and arrays are invalid. Fractional numbers are allowed but not recommended. |

No other top-level members are allowed. A request object with any other member
is an Invalid Request.

**Validation order.** The service checks a request in this order and reports
the first failure:

1. The body is valid UTF-8 JSON, otherwise `-32700` Parse error.
2. The value is an object, or a nonempty array of objects, otherwise `-32600`.
3. `jsonrpc`, `method`, and `id` are present with valid types and there are no
   extra members, otherwise `-32600`.
4. If `params` is present it is an object or an array, otherwise `-32600`
   (the JSON-RPC 2.0 rule: params must be a structured value).
5. `method` names a known method, otherwise `-32601`.
6. `params` matches the method's parameter rules, otherwise `-32602`. This
   includes array-form params, which are valid JSON-RPC but not accepted by
   any method in this API.
7. The method runs. LAMBDA failures map to `-32010` to `-32014` and unexpected
   failures map to `-32603`.

### 2.2 Response object

Each response contains **either** `result` **or** `error`, never both.

Success:

```json
{"jsonrpc": "2.0", "result": {"type": "sint"}, "id": 1}
```

Error:

```json
{"jsonrpc": "2.0", "error": {"code": -32011, "message": "Type error", "data": {"detail": "unbound variable 'x'"}}, "id": 1}
```

| Member | Rule |
| --- | --- |
| `jsonrpc` | Always `"2.0"`. |
| `result` | Present only on success. Its shape depends on the method (§3). |
| `error.code` | Integer (§4). |
| `error.message` | Short, fixed, human-readable summary string. |
| `error.data` | Optional object with structured, client-safe details (§4). It never contains tracebacks, Python exception class names, or filesystem paths. |
| `id` | The request's `id`, unchanged in type and value. It is `null` when the request's `id` could not be determined: unparseable JSON, a non-object request, or a missing or invalid `id` in an otherwise invalid request. |

### 2.3 Request IDs

The `id` is chosen by the client and copied into the response unchanged:
`"abc"` stays a string, `7` stays a number, and `null` stays `null`. Clients use
it to match responses to requests. The server attaches no other meaning to it
and does not require IDs to be unique within a batch.

### 2.4 Notifications

A request **without an `id` member** is a notification, meaning the client
does not want a reply. A request with `"id": null` is **not** a notification;
it is a call whose response carries `"id": null`.

- A valid notification is executed, subject to the same limits as a call, but
  produces **no response object**, even if the method fails.
- An *invalid* request that lacks an `id` cannot be recognized as a valid
  notification. It still receives an Invalid Request (`-32600`) response
  with `id: null`.
- A single valid notification receives **HTTP 204** with an empty body.

### 2.5 Batches

A batch is a JSON array of request objects sent in one HTTP request.

- Each member is validated and processed independently. One bad member does
  not affect the others.
- The response is a JSON array containing one response for every valid call
  and one `-32600` response (with `id: null`) for every invalid member. Valid
  notifications are omitted.
- **Clients must match responses by `id`, not by array position.** The server
  makes no ordering promise.
- If every member is a valid notification, the result is **HTTP 204** with an
  empty body.
- An **empty batch** `[]` is itself an Invalid Request and receives a single
  response *object* (not an array): `-32600` with `id: null`.
- A batch may contain at most **25** members. A larger batch is rejected as a
  whole with a single `-32600` response object (`id: null`,
  `data.reason: "batch_too_large"`).
- Members are processed sequentially. Each interpretation has its own deadline.

---

## 3. Methods

All source-carrying methods first call LAMBDA3's parser and type checker
(`d0exp_parse_and_typecheck`). They interpret or compile only if both succeed.

### Common parameters for source methods

| Param | Type | Rules |
| --- | --- | --- |
| `source` | string | Required. Must contain at least one non-whitespace character. At most **65 536 bytes** when UTF-8 encoded. |
| `libraries` | array of strings | Optional, default `[]`. Names from `"list"`, `"optn"`, `"a1sz"`, `"strm"`, with no duplicates. Each named module from `LAMBDA3/mylib/` is loaded with `d0cls_parse`, and its declarations wrap the source expression (`D0Elets`) in the order given before type-checking. |

Unknown parameter names are rejected with `-32602`.

### Method table

| Method | Params | Result | Behavior |
| --- | --- | --- | --- |
| `service.health` | `{}` (or omitted) | `{"status": "ok", "version": "1.0"}` | Liveness check. Does not touch LAMBDA3. |
| `lambda.typecheck` | `{"source", "libraries"?}` | `{"type": string}` | Parses and type-checks. `type` is `format_type(t)`. |
| `lambda.interpret` | `{"source", "libraries"?}` | `{"type": string, "value": string}` | Parses, type-checks, then evaluates with `d0exp_evaluate` in a separate worker process with a hard deadline (§5). `value` is `d0val_format(v)`. |
| `lambda.compile` | `{"source", "target", "libraries"?}` | `{"target": string, "code": string}` | Parses, type-checks, then calls `d0exp_compile` (`"python"`) or `d0exp_compile_js` (`"javascript"`). `target` must be exactly one of those two strings. `code` is the generated source, returned unchanged. **The generated code is never executed by the service.** |

### Result details

- **Types** are LAMBDA3's own rendering via `format_type`, for example `sint`,
  `bool`, `unit`, `(sint, bool)`, `List[sint]`, `sint -> sint`.
- **Values** are LAMBDA3's own rendering via `d0val_format`, for example
  `42`, `true`, `()`, `(1, true)`, `[1, 2]`. Function values are rendered as
  `<lam>` or `<fix>`. Closures and environments are never serialized.
- **`print` output.** LAMBDA's `print` writes to standard output inside the
  worker process. That output is discarded and is not part of the result.

---

## 4. Errors

### 4.1 Error code table

| Code | `message` | Category | When | `data` |
| --- | --- | --- | --- | --- |
| `-32700` | `Parse error` | JSON-RPC standard | Body is not valid JSON or not valid UTF-8 | `{"reason": "invalid_json"}` or `{"reason": "invalid_utf8"}` |
| `-32600` | `Invalid Request` | JSON-RPC standard | Not a request object; bad `jsonrpc`, `method`, `id`, or `params` type; extra members; empty or oversized batch | `{"reason": string, "member"?: string}` |
| `-32601` | `Method not found` | JSON-RPC standard | Unknown method name | `{"method": string}` |
| `-32602` | `Invalid params` | JSON-RPC standard | Missing, blank, wrongly typed, or oversized `source`; bad `target`; bad `libraries`; unknown param names; array-form params | `{"param": string, "reason": string, ...}` |
| `-32603` | `Internal error` | JSON-RPC standard | Unexpected server failure. Details are logged on the server only. | omitted |
| `-32010` | `LAMBDA syntax error` | Application | LAMBDA3 raised `LambdaSyntaxError` | `{"detail": string, "line": int, "column": int, "text": string}` |
| `-32011` | `LAMBDA type error` | Application | LAMBDA3 raised `TypeCheckError`, including unbound variables | `{"detail": string}` |
| `-32012` | `Execution timeout` | Application | Interpretation passed its deadline and the worker was terminated | `{"timeoutSeconds": number}` |
| `-32013` | `LAMBDA runtime error` | Application | A well-typed program failed while being evaluated, for example `list_head` of an empty list or division by zero | `{"detail": string}` |
| `-32014` | `Stack limit exceeded` | Application | LAMBDA3 ran out of Python call stack (`RecursionError`) at any stage: parsing, type-checking, evaluation, or compilation | `{"stage": "parse" \| "typecheck" \| "evaluate" \| "compile", "detail": string}` |

Notes:

- A LAMBDA **source syntax error is `-32010`, never `-32700`**. `-32700` is
  only for a broken JSON-RPC payload.
- `line` and `column` in `-32010` data are 1-based and refer to the
  `source` parameter. `text` is that source line.
- Values of `data.reason` for `-32600`: `not_an_object`, `empty_batch`,
  `batch_too_large`, `bad_jsonrpc`, `bad_method`, `bad_id`, `bad_params`,
  `unexpected_member` (with `member` naming it).
- Values of `data.reason` for `-32602`: `missing`, `wrong_type`, `blank`,
  `too_large` (adds `limitBytes` and `actualBytes`), `unsupported_target`
  (adds `allowed`), `unknown_library` (adds `allowed`), `duplicate_library`,
  `unexpected_param`, `not_an_object`.
- `-32013` details are LAMBDA-level messages such as
  `"list_head: nonempty list expected"`.
- `-32014` is separate from `-32013` because it is a known limitation of
  the provided implementation rather than a fault in the LAMBDA program.
  LAMBDA3's parser, type checker, interpreter, and compilers all recurse on the
  Python call stack, which is limited (Python's default recursion limit is
  1000), so a valid program can still exceed it. Measured examples: about
  300 nested parentheses (`((…1…))`, around 600 bytes) overflow the
  **parser**, and a non-tail-recursive LAMBDA function such as
  `sum(n) = n + sum(n - 1)` overflows the **evaluator** somewhere between
  100 levels (works) and 150 levels (fails). The exact threshold depends
  on the program's shape. The service does not change
  LAMBDA3 or raise the interpreter's limit. `stage` tells the client
  where the overflow happened, and `detail` is always
  `"Python call stack exhausted"`.
- Unlike a timeout, a stack-limit error is deterministic. The same source
  fails the same way every time.
- A timeout does **not** prove that the program never terminates. It only
  means the program did not finish within the limit.

### 4.2 Information handling

Error responses never contain stack traces, Python exception class names,
module paths, or filesystem paths. Unexpected exceptions are logged on the
server, with traceback, and the client receives only `-32603 Internal error`
with its request `id`.

---

## 5. Limits

| Limit | Value | Enforcement |
| --- | --- | --- |
| Request body size | 2 MiB | HTTP `413` before JSON parsing |
| `source` size | 65 536 bytes (UTF-8) | `-32602`, `reason: "too_large"` |
| Batch size | 25 members | `-32600`, `reason: "batch_too_large"` |
| Interpretation time | **5 seconds** wall-clock per `lambda.interpret` call (configurable at startup with `LAMBDA_RPC_TIMEOUT`) | `-32012` |
| Recursion depth | Python's default recursion limit (1000 frames), inherited from LAMBDA3 and not changed | `-32014` |

**Why a worker process.** The LAMBDA3 interpreter is recursive and has no
step budget, so a running evaluation cannot be safely interrupted inside the
server process. Each `lambda.interpret` call evaluates in a separate process.
If the deadline passes, that process is terminated and the client receives
`-32012`. Parsing and type-checking happen in the server *before* the worker
starts, so syntax and type errors are reported immediately.

For scale: a naive `fib(22)` takes about 3.5 s in this interpreter, while
`fib(25)` exceeds the default deadline.

---

## 6. Examples

All examples are `POST /rpc` with `Content-Type: application/json`. Unless
stated otherwise the HTTP status is `200 OK`.

### 6.1 Health

```json
{"jsonrpc": "2.0", "method": "service.health", "params": {}, "id": "health-1"}
```

```json
{"jsonrpc": "2.0", "result": {"status": "ok", "version": "1.0"}, "id": "health-1"}
```

### 6.2 Successful type-check

```json
{"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "(1, true)"}, "id": 2}
```

```json
{"jsonrpc": "2.0", "result": {"type": "(sint, bool)"}, "id": 2}
```

### 6.3 Successful interpretation (factorial)

```json
{
  "jsonrpc": "2.0",
  "method": "lambda.interpret",
  "params": {
    "source": "let fact : sint -> sint =\n  fix fact(n: sint): sint =>\n    if n <= 1 then 1 else n * fact(n - 1)\nin fact(6) end"
  },
  "id": 3
}
```

```json
{"jsonrpc": "2.0", "result": {"type": "sint", "value": "720"}, "id": 3}
```

Interpretation that uses a library module:

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "list_range(1, 4)", "libraries": ["list"]}, "id": 4}
```

```json
{"jsonrpc": "2.0", "result": {"type": "List[sint]", "value": "[1, 2, 3]"}, "id": 4}
```

A function value:

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "let f : sint -> sint = lam (x: sint) => x in f end"}, "id": 5}
```

```json
{"jsonrpc": "2.0", "result": {"type": "sint -> sint", "value": "<lam>"}, "id": 5}
```

### 6.4 Compilation

```json
{"jsonrpc": "2.0", "method": "lambda.compile", "params": {"source": "1 + 2", "target": "python"}, "id": "py"}
```

```json
{
  "jsonrpc": "2.0",
  "result": {
    "target": "python",
    "code": "…runtime helpers…\ndef _lambda_main():\n    _v1 = 1\n    _v2 = 2\n    _v3 = (_v1 + _v2)\n    return _v3\n\n_lambda_result = _lambda_main()\n"
  },
  "id": "py"
}
```

The `code` string is shortened here. The real response starts with LAMBDA3's
runtime helper definitions. With `"target": "javascript"` the result is
`{"target": "javascript", "code": "…function _lambda_main() {\n  let _v1 = 1;\n  …"}`.

### 6.5 LAMBDA syntax error

```json
{"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "if then"}, "id": "syntax"}
```

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32010,
    "message": "LAMBDA syntax error",
    "data": {"detail": "Expected an expression", "line": 1, "column": 4, "text": "if then"}
  },
  "id": "syntax"
}
```

### 6.6 LAMBDA type errors

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "1 + true"}, "id": "type"}
```

```json
{"jsonrpc": "2.0", "error": {"code": -32011, "message": "LAMBDA type error", "data": {"detail": "+: expected bool, got sint"}}, "id": "type"}
```

An unbound variable is rejected by the type checker. The program is never run.

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "x + 1"}, "id": "unbound"}
```

```json
{"jsonrpc": "2.0", "error": {"code": -32011, "message": "LAMBDA type error", "data": {"detail": "unbound variable 'x'"}}, "id": "unbound"}
```

### 6.7 Runtime error, stack limit, and timeout

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "list_head(list_nil())"}, "id": "rt"}
```

```json
{"jsonrpc": "2.0", "error": {"code": -32013, "message": "LAMBDA runtime error", "data": {"detail": "list_head: nonempty list expected"}}, "id": "rt"}
```

Stack limit during evaluation (the program is well-typed and terminates, but
recurses too deeply for LAMBDA3's recursive interpreter):

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "let sum : sint -> sint = fix sum(n: sint): sint => if n <= 0 then 0 else n + sum(n - 1) in sum(1000) end"}, "id": "deep"}
```

```json
{"jsonrpc": "2.0", "error": {"code": -32014, "message": "Stack limit exceeded", "data": {"stage": "evaluate", "detail": "Python call stack exhausted"}}, "id": "deep"}
```

Stack limit during parsing (300 nested parentheses around `1`):

```json
{"jsonrpc": "2.0", "error": {"code": -32014, "message": "Stack limit exceeded", "data": {"stage": "parse", "detail": "Python call stack exhausted"}}, "id": "nested"}
```

Timeout:

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "let fib : sint -> sint = fix fib(n: sint): sint => if n < 2 then n else fib(n - 1) + fib(n - 2) in fib(30) end"}, "id": "slow"}
```

```json
{"jsonrpc": "2.0", "error": {"code": -32012, "message": "Execution timeout", "data": {"timeoutSeconds": 5.0}}, "id": "slow"}
```

### 6.8 Envelope errors

Malformed JSON, with raw body `{"jsonrpc":`:

```json
{"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error", "data": {"reason": "invalid_json"}}, "id": null}
```

Wrong protocol version (the `id` is discarded because the request is invalid):

```json
{"jsonrpc": "1.0", "method": "service.health", "id": 1}
```

```json
{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request", "data": {"reason": "bad_jsonrpc"}}, "id": null}
```

Unknown method:

```json
{"jsonrpc": "2.0", "method": "does.not.exist", "params": {}, "id": 9}
```

```json
{"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found", "data": {"method": "does.not.exist"}}, "id": 9}
```

Invalid params (blank source):

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "   "}, "id": 10}
```

```json
{"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid params", "data": {"param": "source", "reason": "blank"}}, "id": 10}
```

### 6.9 Batch with calls and a notification

Request:

```json
[
  {"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "6 * 7"}, "id": "answer"},
  {"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "x + 1"}, "id": "bad"},
  {"jsonrpc": "2.0", "method": "service.health", "params": {}},
  "not-a-request-object"
]
```

Response (HTTP 200). The notification has no entry. The invalid member gets
`id: null`. Order is not guaranteed.

```json
[
  {"jsonrpc": "2.0", "result": {"type": "sint", "value": "42"}, "id": "answer"},
  {"jsonrpc": "2.0", "error": {"code": -32011, "message": "LAMBDA type error", "data": {"detail": "unbound variable 'x'"}}, "id": "bad"},
  {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request", "data": {"reason": "not_an_object"}}, "id": null}
]
```

### 6.10 Notification-only batch

```json
[
  {"jsonrpc": "2.0", "method": "service.health", "params": {}},
  {"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "1 + 2"}}
]
```

Response: **HTTP 204 No Content**, empty body. A single notification such as
`{"jsonrpc": "2.0", "method": "service.health", "params": {}}` gets the same
response.

### 6.11 Empty batch

```json
[]
```

```json
{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request", "data": {"reason": "empty_batch"}}, "id": null}
```

---

## 7. JSON Schema

The machine-readable schema is in [`rpc.schema.json`](./rpc.schema.json)
(JSON Schema draft 2020-12). It defines:

- `#/$defs/request`: a single request envelope, with method-specific `params`.
- `#/$defs/batchRequest`: a nonempty array of request members.
- `#/$defs/response`: a success **or** error response, never both.
- `#/$defs/batchResponse`: an array of responses.
- Per-method result shapes and the error-code enumeration.

The schema describes what a **valid** request looks like. Section 2.1 describes
how the server *responds* to an invalid one. The test suite validates the
example payloads in this document and live server responses against the schema.
