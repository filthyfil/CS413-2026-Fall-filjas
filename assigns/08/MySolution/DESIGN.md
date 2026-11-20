# Design: Animated N-Queens Search with CPS and Lazy Streams

> **Note on timing.** The spec asks for this document before
> implementation. The design was worked out first (it follows the spec's
> pseudocode closely), but this file was written up after the code, so it
> describes the design as implemented. File and function names below refer
> to real code.

## 1. Architecture

```
 ┌───────────────────────────── Browser (client/) ─────────────────────────────┐
 │  main.js ── wiring: buttons, keys, speed, size, log, banner                 │
 │     │                                                                       │
 │  player.js ── state machine + small event buffer; pulls a batch only when   │
 │     │          the buffer is empty (4 for Step / 16 for Play / 32 for Seek) │
 │     │                                    board.js ◄── renders each event's  │
 │  rpc.js ── JSON-RPC 2.0 over fetch,                    board snapshot       │
 │     │       typed errors, timeout                      events.js (pure)     │
 └─────┼───────────────────────────────────────────────────────────────────────┘
       │  POST /rpc   application/json   {"method":"queens.next","params":{...}}
       ▼
 ┌───────────────────────────── Python (queens_rpc/) ──────────────────────────┐
 │  app.py      HTTP endpoint (Flask): media type, body size, 200/204/4xx      │
 │     │                                                                       │
 │  jsonrpc.py  RPC dispatcher: envelope validation, fixed method registry,    │
 │     │        error objects, notifications, batches                          │
 │  service.py  queens.open / next / close, service.health; param validation   │
 │     │                                                                       │
 │  streams.py  STREAM TABLE  { uuid → Entry(EventStream, last_used, lock) }   │
 │     │                                                                       │
 │  solver.py   LAMBDA3 bridge: EventStream.take(n) forces ≤ n cells and       │
 │     │        converts each event tuple to JSON; keeps the unforced tail     │
 └─────┼───────────────────────────────────────────────────────────────────────┘
       │  d0exp_evaluate("lazy_eval(s)")           (only two fixed expressions)
       ▼
 ┌──────────────────────── LAMBDA3 (solver/queens_cps.lam) ────────────────────┐
 │  queens_events(size) : Strm[Event]                                          │
 │    LAZY STREAM   cell ── head: (kind, col, row, board)                      │
 │                      └── tail: suspension ──► calls the next continuation   │
 │    CPS SOLVER    try_column / search / check_safe / on_solution /           │
 │                  root_exhausted                                             │
 └─────────────────────────────────────────────────────────────────────────────┘
```

Each layer knows only the one below it. The solver knows nothing about HTTP.
`solver.py` knows nothing about JSON-RPC. `jsonrpc.py` (reused from
Assign07) knows nothing about queens. The client's playback logic has no
DOM code.

## 2. Solver state and invariant

A **partial board** is a `List[sint]` with one queen column per filled row,
**newest row first**: `[5, 2, 0]` means row 0 → column 0, row 1 → column 2,
row 2 → column 5. The bridge reverses it to row order for JSON.

*Why newest first:* placing a queen is a single `list_cons`, and the safety
check walks from the nearest row outward with row distance 1, 2, 3, …,
which is exactly what the diagonal test needs.

**Invariant** for a board of length *r* searched with size *n*:

1. it holds queens for rows `0 … r−1`, exactly one per row;
2. every column is in `0 … n−1`;
3. no two queens share a column or a diagonal.

`place` only runs after `check_safe` succeeds, so the invariant is preserved.
Rows can never collide, because each placement fills the next row.

The rest of the search state is not a data structure. It is the chain of
continuations: the success continuation, and a failure continuation that
closes over the current row, column and board.

## 3. Event schema

LAMBDA3 has no strings or variants, so an event is a tuple
`(kind, column, row, board)` with an integer kind code. The bridge
(`solver.decode_event`) converts it to JSON:

| Code | Event | JSON | Board |
| --- | --- | --- | --- |
| 0 | `try` | `{"event":"try","column":c,"row":r,"board":[…]}` | current partial board (length r) |
| 1 | `place` | `{"event":"place","column":c,"row":r,"board":[…]}` | updated board, including the new queen |
| 2 | `reject` | `{"event":"reject","column":c,"row":r,"board":[…]}` | current board, unchanged |
| 3 | `backtrack` | `{"event":"backtrack","column":c,"row":r,"board":[…]}` | restored board, without (r, c) |
| 4 | `solution` | `{"event":"solution","board":[…]}` | complete board (length n) |
| 5 | `done` | `{"event":"done"}` | none |

Boards in JSON are arrays of columns in row order, zero-based. `done`
appears exactly once, as the last event. Every `try` is answered by exactly
one `place` or `reject` for the same square. Every `place` is eventually
matched by a `backtrack` for the same square.

## 4. CPS continuations

Let `E` be the event tuple type and `Strm[E] = Lazy[Stcn[E]]`.

| Continuation | Type | Role |
| --- | --- | --- |
| `on_solution` | `(List[sint], unit -> Strm[E]) -> Strm[E]` | receives a complete board **and** the failure continuation that resumes the search after it |
| `on_exhausted` (failure) | `unit -> Strm[E]` | what to do when the current choice point has no candidates left |
| `on_safe`, `on_conflict` | `unit -> R` | `check_safe[R]` is polymorphic; the solver uses `R = Strm[E]`, and the tests use `bool` and `sint` |

Every function's answer type is the stream itself. None of them returns a
board or a Boolean for direct-style code to inspect. All calls to
continuations, and all recursive calls, are in tail position.

### Trying a candidate and resuming (as implemented)

```text
check_safe(column, distance, board, on_safe, on_conflict):     # CPS, no Boolean result
  if board = []                                  then on_safe()
  else if attacks(column, distance, head(board)) then on_conflict()   # stop at first collision
  else check_safe(column, distance + 1, tail(board), on_safe, on_conflict)

try_column(size, row, column, board, on_solution, on_exhausted):
  next_column = λ(). try_column(size, row, column + 1, board, on_solution, on_exhausted)
  search      = λ(r, b, fail). if r = size then on_solution(b, fail)
                               else try_column(size, r, 0, b, on_solution, fail)
  if column = size then on_exhausted()                     # row exhausted → failure continuation
  else emit(try(column, row, board), λ().
         check_safe(column, 1, board,
           λ(). let next = place(column, board) in              # on_safe
                emit(place(column, row, next), λ().
                  search(row + 1, next,
                    λ(). emit(backtrack(column, row, board), next_column))),  # new failure cont.
           λ(). emit(reject(column, row, board), next_column)))   # on_conflict

on_solution(board, resume) = emit(solution(board), resume)        # tail = rest of the search
root_exhausted()           = emit(done, λ(). empty_stream)
queens_events(size)        = lazy(λ(). force(search(size, 0, [], on_solution, root_exhausted)))
```

LAMBDA3's `fix` binds a single name, so `search` is a local closure inside
`try_column` rather than a mutually recursive top-level function. A
top-level `search` with the same contract serves as the entry point.

### How the continuations encode the search order

- **Left to right:** the only way to move on within a row is
  `next_column`, which calls `try_column` with `column + 1`.
- **Depth first:** after `place`, control goes to the next row (`search`)
  *before* anything else. The next column of the current row is reached
  only through the failure continuation built at that moment.
- **Backtracking:** that failure continuation (`λ(). emit(backtrack …,
  next_column)`) closes over the *current* row, column and board. When the
  subtree below the queen is exhausted (every column of the deeper row
  fails) the deeper `try_column` calls it, and it records the backtrack
  with the restored board and resumes at the next column one level up.
- **After a solution:** `on_solution` receives the innermost failure
  continuation as `resume` and makes it the stream's tail. Asking for more
  events after a solution therefore continues exactly where the search
  stopped. The first thing it does is backtrack the last queen.
- **Termination:** at row 0 the failure continuation is `root_exhausted`,
  which emits `done` once and then ends the stream.

The tests show this is real CPS, not a wrapper around a direct-style
solver. Supplying different continuations changes the stream mid-search,
for example a success continuation that stops after the first solution
(`test_cps_search.py`).

## 5. From CPS to a lazy stream

```text
emit(event, k) = lazy(λ(). cons(event, lazy(λ(). force(k()))))
```

`emit` builds one stream cell whose tail is a **fresh suspension** wrapping
the continuation. Every continuation's body ends in a call to `emit`, or to
another continuation that does, so a continuation returns an unforced cell
right away.

**Work done when a cell is forced.** Forcing the *head* cell just builds
`cons(event, <suspension>)` and runs no search. Forcing a *tail* runs the
continuation `k` up to its next `emit`. That is exactly one search step:

| After event | Forcing the tail runs | Cost |
| --- | --- | --- |
| `try` | `check_safe` against earlier rows → emit `place` or `reject` | ≤ row `attacks` tests |
| `place` | `search(row + 1)` → emit `try` (or `solution` if the board is full) | O(1) |
| `reject`, `backtrack` | `next_column` → emit `try`, or (row exhausted) the failure continuation → emit `backtrack` / `done` | O(1) |
| `solution` | `resume` (failure continuation) → emit `backtrack` | O(1) |
| `done` | → empty stream | O(1) |

So one forced cell costs at most one row's safety check (< *n* tests), and
nothing beyond the requested cell is evaluated. `queens_events(size)` wraps
everything in one more suspension, so **opening a stream performs no search
at all**. Even the first `try` is built only when cell 0 is forced.

LAMBDA3 memoizes `lazy` values, so forcing an already forced cell repeats
no work. The Python stack also stays shallow: each suspension returns after
one step, so no chain of earlier forcing builds up. The measured maximum is
122 frames over 3,000 events on 10×10.

**Bridge.** `EventStream` (`solver.py`) holds the unforced remainder of the
stream as `cursor`. `take(n)` evaluates the fixed expression `lazy_eval(s)`
at most *n* times, decodes each head, and moves the cursor to the last
tail, which it never forces. After `done` it drops the cursor.

## 6. RPC methods

One endpoint: `POST /rpc`, `Content-Type: application/json`, JSON-RPC 2.0.
The method registry is a fixed dict: `service.health`, `queens.open`,
`queens.next`, `queens.close`. No request can name another function or
send source code. The solver source is a fixed file loaded and type-checked
once at startup.

**`service.health`**
```json
→ {"jsonrpc":"2.0","method":"service.health","params":{},"id":1}
← {"jsonrpc":"2.0","result":{"status":"ok","version":"1.0"},"id":1}
```

**`queens.open`**: `size` is an integer from 4 to 10. It returns without
forcing the stream.
```json
→ {"jsonrpc":"2.0","method":"queens.open","params":{"size":8},"id":2}
← {"jsonrpc":"2.0","result":{"stream_id":"475e2227-5099-4b12-b92c-acde9ac880cf","size":8},"id":2}
```

**`queens.next`**: `limit` is an integer from 1 to 32, default 1. It
forces at most `limit` cells. `done` is `true` in the response that
contains the `done` event and in every later response.
```json
→ {"jsonrpc":"2.0","method":"queens.next","params":{"stream_id":"475e2227-…","limit":3},"id":3}
← {"jsonrpc":"2.0","result":{"events":[
     {"event":"try","column":0,"row":0,"board":[]},
     {"event":"place","column":0,"row":0,"board":[0]},
     {"event":"try","column":0,"row":1,"board":[0]}],"done":false},"id":3}

   … the last batch of an 8×8 run with limit 32 (33,589 events → 21 left):
← {"jsonrpc":"2.0","result":{"events":[…19 events…,
                                       {"event":"backtrack","column":7,"row":0,"board":[]},
                                       {"event":"done"}],"done":true},"id":1052}
   … and afterwards:
← {"jsonrpc":"2.0","result":{"events":[],"done":true},"id":1053}
```

**`queens.close`**
```json
→ {"jsonrpc":"2.0","method":"queens.close","params":{"stream_id":"475e2227-…"},"id":4}
← {"jsonrpc":"2.0","result":{"closed":true},"id":4}
```

## 7. Stream lifetime, cleanup, and limits

| Aspect | Behaviour |
| --- | --- |
| IDs | `str(uuid.uuid4())`: 122 random bits, unguessable within the process |
| Atomicity | Each entry has its own lock, held for the whole `take`. Concurrent `next` calls on one ID run one after another, and different IDs run in parallel. The table lock guards only the dict and is never held while forcing. |
| All-or-nothing `next` | The cursor advances only after every requested cell was forced and decoded. If a failure happens midway, the stream stays where it was. Memoization makes a retry cheap and returns the same events. |
| Exhaustion | When `done` is produced, the lazy stream is released immediately (`cursor = None`). The ID stays as a tiny tombstone, so repeated `next` calls return `{"events":[],"done":true}` as the spec requires, until `close` or expiry. |
| `close` | Removes the entry. A later `next` or `close` gets −32001. The browser closes on Reset, on completion, and on `pagehide` (a keepalive notification). |
| Inactivity lifetime | **300 s** since the last `open`/`next` (env `QUEENS_STREAM_TTL`). Expired entries are swept on *every* table operation, so no background thread is needed. The clock is injectable for tests. |
| Capacity | At most **64** streams, after sweeping expired ones; otherwise −32002. |
| Other limits | `size` 4–10, `limit` 1–32, request body ≤ 64 KB (HTTP 413), batch ≤ 25 items, `stream_id` 1–64 characters. |
| Restarts | All state is process-local. A restart invalidates every ID (−32001), and the client offers Restart. |

## 8. Errors and validation

Validation order: transport (HTTP method, media type, size) → JSON parse →
envelope → method name → params. Everything is validated **before** a
stream is allocated.

| Code | When | `data` |
| --- | --- | --- |
| −32700 | body is not valid UTF-8 JSON (NaN/Infinity rejected too) | `{"reason"}` |
| −32600 | envelope wrong: not an object, `jsonrpc` ≠ "2.0", non-string method, bad id type, non-structured params, extra members, empty or oversized batch | `{"reason"}`; reply id is `null` |
| −32601 | method not in the registry | `{"method"}` |
| −32602 | params not an object, unexpected key, missing / wrong type / out of range (`true` and `8.0` are rejected as sizes) | `{"param","reason"[,"min","max"]}` |
| −32603 | any unexpected exception | none; the message is the fixed "Internal error", and the traceback goes only to the server log |
| **−32001** | **Unknown stream**: ID never issued, closed, or expired (deliberately indistinguishable) | `{"stream_id","reason":"unknown_closed_or_expired"}` |
| **−32002** | **Too many open streams** | `{"limit"}` |

Responses never contain tracebacks, paths, or interpreter values. The
bridge converts every event to plain JSON, and the tests scan responses for
leak markers such as `D0V`, `<lazy>`, `Traceback` and `/home/`.

**HTTP statuses:** every JSON-RPC reply (success or error) is 200. A
notification, or a batch of only notifications, is **204** with an empty
body. Transport problems use 404/405/413/415 with plain text.

**Notifications** are executed for their effect. A `queens.next`
notification consumes events silently, and a `queens.close` notification
closes. A `queens.open` notification creates a stream whose ID nobody
learns; it costs no search and expires after the TTL.

**Batches** (optional feature): up to 25 items, processed **in order**, one
at a time, each against the current stream table. Several `queens.next`
items for one stream therefore return consecutive slices. An ID created by
`queens.open` cannot be used later in the same batch, because the client
learns it only from the batch response.

## 9. Browser client

- **rpc.js** classifies failures as `network` / `http` / `protocol` / `rpc`
  and rejects a `next` result containing more events than requested.
- **player.js** states: `idle → opening → ready ⇄ playing / seeking →
  finished`, plus `error`. It fetches only when its buffer is empty and
  never prefetches while idle. At most one request is in flight. A
  generation counter discards responses that arrive after a Reset.
  `retry()` resumes on the same stream unless the error was −32001, in
  which case it reopens.
- **board.js** draws each event from its own board snapshot, so rendering
  never depends on earlier events. For `reject` it highlights the attacking
  queen and the squares between, using `events.conflicts` and
  `events.attackPath`.
- Completion (`done`, dimmed board plus a "Search complete" banner) is
  styled differently from a solution (gold glow).
