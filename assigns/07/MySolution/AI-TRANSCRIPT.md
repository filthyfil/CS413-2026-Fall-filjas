# AI Use Record: Assignment 7 (LAMBDA3 JSON-RPC Service)

## Tool

**Claude Code** (Anthropic, model Claude Opus 5.5), used in the terminal in
a single session on 2026-11-10. The AI:

- read the assignment, the provided LAMBDA3 code, and the provided tests;
- wrote code and documents into `MySolution/`;
- ran LAMBDA3 directly to check its behavior, ran the server, and ran the
  test suites and mypy.

Of course, I asked the AI to first remind me about the RPC and then RPC vs REST. I understand the details, and proceed with the implementation.

## Important prompts and what came out of them

Prompts are quoted as typed.

1. **"Hi please read assign07"**
   The AI read `Assign07.md`, `TEST/test_rpc_api.py`, and the structure of
   `lambda3.py`. It summarized the methods, error codes, HTTP rules, limits,
   and deliverables. It pointed out that `MySolution/` was empty on the due
   date, and that the provided tests pin exact outputs (for example
   `(sint, bool)`, `List[sint]`, `<lam>`).

2. **"lets talk about what RPC is and how it is different from REST"**,
   **"a client sends basically a jsonify of the function call; what is
   returned?"**, **"how is the json packaged over http"**
   Conceptual explanations, no code:
   - RPC exposes verbs at one endpoint; REST exposes resources at many URLs.
   - A response is `{result, id}` or `{error, id}`, never both.
   - Notifications get no reply, and batches get an array.
   - How the JSON body sits inside an HTTP request and response.
   - Why an RPC error still uses HTTP 200: the transport layer worked, and
     the failure belongs to the application layer.

3. **"ok lets start with RPC.md"**
   Before writing the contract, the AI ran LAMBDA3 under Python 3.12 so the
   examples would be real outputs rather than guesses. It found that:
   - the system `python3` is 3.10, which cannot import `lambda3.py`;
   - `fib(22)` takes about 3.5 s, which informed the 5 s deadline;
   - well-typed programs can still fail at run time (`list_head(list_nil())`,
     `1 / 0`).

   **Design choices the AI proposed and listed for approval:**
   - an extra code `-32013` for LAMBDA runtime errors;
   - an optional `libraries` parameter for the `mylib` modules;
   - the limits (64 KiB source, 2 MiB body, 25-item batches, 5 s);
   - strict envelope and params validation;
   - discarding `print` output.

   It wrote `RPC.md` and `rpc.schema.json`.

4. **"Since the recursion limit it well known limitation, and I cannot edit
   the LAMBDA3. create its own special class of runtime error. called stack
   limit error."**
   The AI added `-32014 Stack limit exceeded`. Before writing it up, it
   checked where the limit is reached. That showed the stack limit applies
   to every stage, not just evaluation:
   - about 300 nested parentheses (around 600 bytes) overflow the **parser**;
   - non-tail recursion overflows the **evaluator** between depth 100 and
     150 (an earlier guess of "a few hundred" was measured and corrected).

   So the error carries `data.stage` (`parse`/`typecheck`/`evaluate`/`compile`).

5. **"ok start the flask implementation"**
   The AI wrote the `lambda_rpc` package in layers:
   - `app.py`: transport;
   - `jsonrpc.py`: envelope and dispatch, with no Flask or LAMBDA3 imports;
   - `service.py`: methods and validation;
   - `frontend.py`: LAMBDA3 loading;
   - `worker.py`: interpretation in a child process using `forkserver`,
     killed at the deadline.

   All 15 provided black-box tests passed on the first run. The AI then
   checked the behaviors those tests don't cover with `curl`, and confirmed
   that a timed-out worker process does not linger.

6. **"now create a test suite; including injected backend failure, timeout,
   and checking if responses make sense."**
   The AI wrote 93 in-process HTTP tests (Flask test client).
   - **"Make sense" checks:** every response is validated against the
     JSON Schema, error responses are scanned for leaked internals, ids
     must keep their JSON type, and generated Python must pass
     `ast.parse` (never executed).
   - **Docs replay:** every request/response example in RPC.md is sent to
     the real service and must match exactly.
   - **Test doubles** are used only for failures: an injected exception
     carrying a fake secret path, and an injected interpreter outcome. The
     timeout is also tested for real with a 0.5 s deadline.
   - **Two failures on the first run, both mistakes in the tests:**
     - `list_head(list_nil())` has type `?t1`, not `sint`;
     - `json.dumps` escaped `…`, so the skip check never matched.

7. **"use the type checker and raise any issues to me and a plan to fix
   them; if they exist; after the tests"**, then **"plan looks good"**
   The AI ran mypy. Of 121 errors, 108 were in the provided LAMBDA3 code and
   13 were ours. It reported these with a fix plan instead of fixing them
   right away. The main issue was that the worker's result type was an
   untyped `(kind, payload: object)` pair, so mistakes between the worker
   and the service could not be caught statically.

   After approval it:
   - replaced that pair with one dataclass per outcome;
   - simplified the runtime-error mapping;
   - renamed a reused exception variable;
   - added annotations, `mypy.ini` (strict for the package, LAMBDA3
     skipped), and `requirements-dev.txt`.

   Result: mypy reports no issues, and all 93 + 15 tests still pass.

8. **"yes, write the README, TESTING, and AI-TRANSCRIPT, leave the human
   parts to me"**
   The AI wrote these three documents. The curl outputs in README.md were
   re-run against the live server. One command was fixed because its output
   began mid-word. The per-file test counts in TESTING.md were checked
   against the actual test list and corrected.

## What the AI verified itself

- LAMBDA3 behavior (types, values, error messages, recursion thresholds,
  timing) was measured directly with Python 3.12 before being written into
  RPC.md or tests.
- Provided black-box suite: 15/15 OK against a live server.
- Own suite: 93/93 OK. mypy (strict): no issues.
- No timed-out worker process remains after a timeout. Checked with `ps`
  during manual testing, and with `multiprocessing.active_children()` in a
  test.

## How I reviewed and tested the result

I think reading the tests is the most important part of vibe coding because its the place where you can validate exactly what you wanted to the AI with a strict testing. Hence, with AI coding, I think this is the area of most emphasis, as well as testing the code as a user.

Naturally, we have some errors that can happen. And since python for example has the known limitation of stack depth when it comes to tail recursive languages, we should be careful around this. Since I do not touch the LAMBDA3, I still want to make sure the user understands what is going on, so instead of just saying "runtime error" I ask AI to make a specific case for the stack limit reached.

## Reflection

Actually, I think I like RPC better than REST. It's more natural to the constructs of the LAMBDA language, and the idea just makes more sense in a programmatic perspective. I do not mean to say that RPC is better than REST in all ways, because this is just not true; there are certainly applications where REST is needed, like Login page.

I think it was interesting to learn about RPC.
