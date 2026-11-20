# Assignment 8: Animated N-Queens Search with CPS and Lazy Streams

A depth-first N-Queens solver written in **LAMBDA3** in continuation-passing
style. Its search trace is a **lazy stream** of events (`try`, `place`,
`reject`, `backtrack`, `solution`, `done`). A small **Flask JSON-RPC 2.0**
service hands those events out a few at a time, and a **plain HTML/CSS/JS**
page requests them on demand and animates them on a chessboard.

Nothing is computed ahead of demand. `queens.open` runs no search at all,
and each `queens.next` forces at most `limit` (≤ 32) stream cells.

See [DESIGN.md](DESIGN.md) for the continuation conventions, the laziness
argument, and the full RPC contract, and [TESTING.md](TESTING.md) for the
requirement → test mapping.

## Requirements

| What | Version | Why |
| --- | --- | --- |
| Python | **3.12 or later** | `lambda3.py` uses PEP 695 `type` statements; it will not even parse on 3.10/3.11 |
| Flask | ≥ 3.0, < 4 | HTTP transport (`requirements.txt`) |
| mypy | ≥ 1.10 | optional type checking (`requirements-dev.txt`) |
| Node.js | ≥ 20 (tested on 22) | only to run the client unit tests; the page itself needs just a browser |

The supplied interpreter in `../LAMBDA3/` is used as-is. It is found
relative to `MySolution/`. To point elsewhere, set
`QUEENS_LAMBDA3_DIR=/path/to/LAMBDA3`.

## Setup

From `assigns/08/MySolution/`:

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt     # Flask + mypy
```

(Or `make venv`. With uv: `uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt`.)

## Run

```sh
.venv/bin/python -m queens_rpc                  # http://127.0.0.1:8000/
.venv/bin/python -m queens_rpc --port 9000      # another port
QUEENS_STREAM_TTL=60 .venv/bin/python -m queens_rpc   # 60 s stream inactivity lifetime
```

Then open **<http://127.0.0.1:8000/>**. The RPC endpoint is
`POST http://127.0.0.1:8000/rpc`. The server binds to localhost only, and
the page needs no external service or account.

## Test

All commands are run from `assigns/08/MySolution/`.

```sh
.venv/bin/python -m unittest discover -s tests -v          # Python: solver, laziness, streams, RPC, HTTP
node --test tests/client/*.test.mjs                        # JS: rpc.js, events.js, player.js
.venv/bin/mypy                                             # strict type check of queens_rpc/ and tests/
```

or `make test` (both suites), `make typecheck`.

The full Python suite takes about **1–2 minutes**. The tree-walking
LAMBDA3 interpreter spends about 1 ms per event, and two tests walk the
entire 8×8 trace (33,589 events), once in-process and once over real HTTP.
For a quick loop, skip just those two:

```sh
QUEENS_SKIP_SLOW=1 .venv/bin/python -m unittest discover -s tests -v    # or: make test-fast
```

Browser UI behaviour is covered by the automated `player.test.mjs` (the
logic behind each control) plus the manual checklist in
[TESTING.md](TESTING.md).

## Using the page

| Control | Key | What it does |
| --- | --- | --- |
| **Start** / **Restart** | `S` | Close any current stream and open a fresh one (no search runs yet) |
| **Step** | `→` | Show the next single event |
| **Play** / **Pause** | `Space` | Timed playback, one event per tick; pause keeps the stream |
| **Next solution** | `N` | Run quickly to the next `solution` (or to `done`) |
| **Reset** | `R` | Close the stream on the server and clear the board |
| Board | | 4×4 … 10×10 (8×8 default); changing it resets |
| Speed | | 1000 ms … 10 ms per event (log scale) |

Step, Play and Next solution open a stream automatically if none is open.

How each event looks:

- **try**: yellow outline with a faded queen on the candidate square; the current row is tinted.
- **place**: the queen joins the board with a green pop.
- **reject**: red outline and ✕. The attacking queen is outlined in red and the squares between them are shaded, so you can see *why* the candidate fails. The status line names the attacker and the line (column or diagonal).
- **backtrack**: purple dashed queen fading out; the board is restored.
- **solution**: the whole board glows gold; the solution is added to the list and the counter goes up.
- **done**: the board dims and a "Search complete: *N* solutions found" banner appears with **Restart search**. This is visibly different from a solution.

The side panel shows counters for solutions, events, each event kind, and
**RPC calls / events fetched / events buffered**. These make the
incremental fetching visible: after Start, *Fetched* is 0. Network and RPC
failures show a red banner. **Retry** continues on the same stream when that
is safe, and **Restart search** always works.

## RPC examples

```sh
rpc() { curl -s http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d "$1"; echo; }

rpc '{"jsonrpc":"2.0","method":"service.health","params":{},"id":1}'
# {"jsonrpc": "2.0", "result": {"status": "ok", "version": "1.0"}, "id": 1}

rpc '{"jsonrpc":"2.0","method":"queens.open","params":{"size":8},"id":2}'
# {"jsonrpc": "2.0", "result": {"stream_id": "475e2227-5099-4b12-b92c-acde9ac880cf", "size": 8}, "id": 2}

rpc '{"jsonrpc":"2.0","method":"queens.next","params":{"stream_id":"475e2227-…","limit":3},"id":3}'
# {"jsonrpc": "2.0", "result": {"events": [
#    {"event": "try",   "column": 0, "row": 0, "board": []},
#    {"event": "place", "column": 0, "row": 0, "board": [0]},
#    {"event": "try",   "column": 0, "row": 1, "board": [0]}], "done": false}, "id": 3}

rpc '{"jsonrpc":"2.0","method":"queens.close","params":{"stream_id":"475e2227-…"},"id":4}'
# {"jsonrpc": "2.0", "result": {"closed": true}, "id": 4}

rpc '{"jsonrpc":"2.0","method":"queens.next","params":{"stream_id":"475e2227-…"},"id":5}'
# {"jsonrpc": "2.0", "error": {"code": -32001, "message": "Unknown stream",
#   "data": {"stream_id": "475e2227-…", "reason": "unknown_closed_or_expired"}}, "id": 5}
```

Boards are arrays of queen columns in row order (rows and columns from 0).
A `solution` event carries only `board`, and `done` carries nothing else.

| Code | Meaning |
| --- | --- |
| -32700 | Parse error (invalid JSON / UTF-8) |
| -32600 | Invalid request (bad envelope) |
| -32601 | Method not found |
| -32602 | Invalid params (`data.param` and `data.reason` say which and why) |
| -32603 | Internal error (no details exposed) |
| **-32001** | Unknown stream: unknown, closed, or expired ID |
| **-32002** | Too many open streams (limit 64) |

Notifications (no `id`) get HTTP 204 with an empty body. Every JSON-RPC
reply, success or error, is HTTP 200. Batches of up to 25 requests are
supported and run in order. Limits: `size` 4–10, `limit` 1–32 (default 1),
request body ≤ 64 KB, streams expire after 300 s of inactivity.

## Layout

```
MySolution/
├── solver/queens_cps.lam     LAMBDA3 CPS search + lazy event stream (the solver)
├── queens_rpc/
│   ├── solver.py             LAMBDA3 bridge: load once, open, force cells, event → JSON
│   ├── streams.py            stream table: UUIDs, per-stream locks, TTL, cleanup
│   ├── jsonrpc.py            JSON-RPC envelope + dispatch (reused from Assign07)
│   ├── service.py            the four methods + parameter validation
│   ├── app.py                Flask: POST /rpc, static client
│   └── __main__.py           python -m queens_rpc
├── client/
│   ├── index.html, app.css
│   ├── rpc.js                transport (JSON-RPC over fetch, typed errors)
│   ├── player.js             playback state machine, on-demand batches
│   ├── board.js              DOM renderer
│   ├── events.js             pure helpers (conflicts, descriptions)
│   └── main.js               wiring
├── tests/                    Python unittest suite + tests/client/*.test.mjs (node:test)
├── requirements.txt, requirements-dev.txt, mypy.ini, Makefile
└── DESIGN.md, README.md, TESTING.md, AI-TRANSCRIPT.md
```

## Limitations

- **Speed.** The supplied LAMBDA3 interpreter walks the AST and takes about
  1 ms per event. A full 8×8 trace takes about 30 s to stream, and 10×10 is
  far longer. Interactive use is unaffected, since one request is at most
  32 events, but end-to-end tests are slow.
- **Process-local state.** Streams live in memory. A server restart
  invalidates every stream ID, and the page then shows the expired-stream
  error with a Restart button. Running several server processes would need
  sticky sessions.
- **No pause/resume across reloads.** Reloading the page starts over; the
  old stream is closed on `pagehide` or expires after its TTL.
- **A `queens.open` sent as a notification** creates a stream whose ID the
  client never learns. It costs no search, since opening is lazy, and it
  expires after the TTL.
- **Development server only.** `python -m queens_rpc` uses Flask's built-in
  threaded server, intended for local use and tests. It has no
  authentication and is not meant for public deployment.
- **Browser UI tests are partly manual.** The control logic is unit-tested
  in Node, but rendering is checked with the manual checklist in
  TESTING.md, not a browser automation tool.
