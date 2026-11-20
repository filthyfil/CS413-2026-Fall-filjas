"""Shared helpers for the Python test suite.

* ``SOLVER``: one loaded LAMBDA3 solver for the whole run.
* ``lam_eval``: evaluate a test expression with the solver's declarations in
  scope (type-checked first), to call CPS functions with custom continuations.
* ``raw_events``: decode a LAMBDA3 stream that may contain test-only marker
  events (kinds 7/8), which the production decoder deliberately rejects.
* ``ApplyCounter``: a trace hook that counts interpreter function
  applications, both overall and per named solver function. It wraps
  ``lambda3._d0val_apply``, which every application and every ``lazy_eval``
  thunk call goes through, so it observes actual search work instead of
  inspecting how a value prints.
* ``reference_trace``: an independent, direct-style Python model of the
  event sequence, used as an oracle.
* ``full_trace``: the cached complete LAMBDA3 trace for a size (8x8 takes
  about 30 s with the tree-walking interpreter).
* ``RpcTestCase``: in-process Flask test client over a real service.
"""

from __future__ import annotations

import functools
import json
import os
import sys
import unittest
from collections import Counter
from pathlib import Path
from typing import Any
from unittest import mock

SOLUTION_DIR = Path(__file__).resolve().parents[1]
if str(SOLUTION_DIR) not in sys.path:
    sys.path.insert(0, str(SOLUTION_DIR))

from queens_rpc import solver as S  # noqa: E402  (puts ../LAMBDA3 on sys.path)
import lambda3 as L  # noqa: E402
from basics0 import fnlist_cons  # noqa: E402
from queens_rpc.app import create_app  # noqa: E402
from queens_rpc.service import QueensService  # noqa: E402

SOLVER = S.QueensSolver()

# The event tuple type, for writing test continuations in LAMBDA3.
E = "(sint, sint, sint, List[sint])"
SKIP_SLOW = os.environ.get("QUEENS_SKIP_SLOW") == "1"
slow = unittest.skipIf(SKIP_SLOW, "QUEENS_SKIP_SLOW=1")

# Things that must never appear in a response body.
LEAK_MARKERS = ("Traceback", 'File "', "/home/", ".py", "lambda3", "D0V", "ENVcns",
                "object at 0x", "<lam>", "<fix>", "<lazy>")


# -- LAMBDA3 helpers -----------------------------------------------------------

def unforced(stream: S.EventStream) -> bool:
    """True when the stream's next cell is a suspension the interpreter has not run."""
    cursor = stream.cursor
    assert cursor is not None, "stream is exhausted"
    return not cursor.evaluated


def lam_eval(source: str) -> Any:
    expr = L.D0Elets(SOLVER.declarations, L.d0exp_parse(source))
    L.d0exp_typecheck(expr)
    return L.d0exp_evaluate(expr)


def lam_list(rows: list[int]) -> str:
    """LAMBDA3 source for a board given in ROW ORDER (stored newest first)."""
    src = "list_nil()"
    for column in rows:
        src = f"list_cons({column}, {src})"
    return src


def raw_events(strm: Any, limit: int = 100_000) -> list[tuple[int, int, int, list[int]]]:
    out: list[tuple[int, int, int, list[int]]] = []
    while len(out) < limit:
        cell = S.force(strm)
        if not cell.is_cons:
            break
        kind, column, row, board = cell.head.arg1
        out.append((kind.arg1, column.arg1, row.arg1, S.board_rows(board)))
        strm = cell.tail
    return out


class ApplyCounter:
    """Context manager counting interpreter applications.

    ``total`` counts every application. ``by_name[f]`` counts calls of the
    solver's top-level function ``f`` (matched by the identity of its AST
    node, so a recursive ``fix`` counts each iteration).
    """

    def __init__(self) -> None:
        self.total = 0
        self.by_name: Counter[str] = Counter()
        self._names = {id(d.arg2): d.arg1 for d in _decls()}
        self._original = L._d0val_apply

    def __enter__(self) -> "ApplyCounter":
        original = self._original

        def counting(fn: Any, arg: Any) -> Any:
            self.total += 1
            name = self._names.get(id(getattr(fn, "arg2", None)))
            if name is not None:
                self.by_name[name] += 1
            return original(fn, arg)

        self._patch = mock.patch.object(L, "_d0val_apply", counting)
        self._patch.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._patch.stop()

    def __getitem__(self, name: str) -> int:
        return self.by_name[name]


def _decls() -> list[Any]:
    out = []
    d = SOLVER.declarations
    while isinstance(d, fnlist_cons):
        out.append(d.arg1)
        d = d.arg2
    return out


# -- reference model -------------------------------------------------------------

def _safe(board: list[int], row: int, column: int) -> bool:
    return all(c != column and abs(c - column) != row - r for r, c in enumerate(board))


def reference_trace(n: int) -> list[dict[str, Any]]:
    """Expected events, written directly from the spec's prose (direct style)."""
    events: list[dict[str, Any]] = []

    def row_search(row: int, board: list[int]) -> None:
        for column in range(n):
            events.append({"event": "try", "column": column, "row": row, "board": board})
            if not _safe(board, row, column):
                events.append({"event": "reject", "column": column, "row": row, "board": board})
                continue
            placed = board + [column]
            events.append({"event": "place", "column": column, "row": row, "board": placed})
            if row + 1 == n:
                events.append({"event": "solution", "board": placed})
            else:
                row_search(row + 1, placed)
            events.append({"event": "backtrack", "column": column, "row": row, "board": board})

    row_search(0, [])
    events.append({"event": "done"})
    return events


def reference_solutions(n: int) -> list[tuple[int, ...]]:
    return [tuple(e["board"]) for e in reference_trace(n) if e["event"] == "solution"]


@functools.cache
def full_trace(n: int) -> tuple[dict[str, Any], ...]:
    """Every event of the LAMBDA3 stream for size n, through the adapter."""
    stream = SOLVER.open(n)
    events: list[dict[str, Any]] = []
    while not stream.exhausted:
        batch, _ = stream.take(32)
        events.extend(batch)
    return tuple(events)


# -- RPC helpers -------------------------------------------------------------------

class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def request(method: str, params: Any = None, request_id: Any = 1, *, notification: bool = False) -> dict[str, Any]:
    req: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        req["params"] = params
    if not notification:
        req["id"] = request_id
    return req


class RpcTestCase(unittest.TestCase):
    ttl_seconds = 60.0
    max_streams = 8

    def setUp(self) -> None:
        self.clock = FakeClock()
        self.service = QueensService(SOLVER, ttl_seconds=self.ttl_seconds,
                                     max_streams=self.max_streams, clock=self.clock)
        self.client = create_app(self.service).test_client()

    def post_raw(self, body: bytes | str, content_type: str = "application/json") -> Any:
        return self.client.post("/rpc", data=body, content_type=content_type)

    def post(self, payload: Any) -> Any:
        return self.post_raw(json.dumps(payload))

    def json_reply(self, response: Any) -> Any:
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.mimetype, "application/json")
        return json.loads(response.get_data(as_text=True))

    def assert_envelope(self, body: Any) -> None:
        self.assertIsInstance(body, dict)
        self.assertEqual(body.get("jsonrpc"), "2.0")
        self.assertIn("id", body)
        self.assertNotEqual("result" in body, "error" in body, body)
        if "error" in body:
            err = body["error"]
            self.assertIsInstance(err.get("code"), int)
            self.assertIsInstance(err.get("message"), str)
            self.assert_no_leak(body)

    def assert_no_leak(self, body: Any) -> None:
        text = json.dumps(body)
        for marker in LEAK_MARKERS:
            self.assertNotIn(marker, text, f"response leaks {marker!r}")

    def assert_no_reply(self, response: Any) -> None:
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.get_data(), b"")

    def call(self, method: str, params: Any = None, request_id: Any = 1) -> dict[str, Any]:
        body = self.json_reply(self.post(request(method, params, request_id)))
        self.assert_envelope(body)
        result: dict[str, Any] = body
        return result

    def ok(self, method: str, params: Any = None, request_id: Any = 1) -> Any:
        body = self.call(method, params, request_id)
        self.assertEqual(body["id"], request_id)
        self.assertIn("result", body, body)
        return body["result"]

    def fails(self, method: str, params: Any, code: int, request_id: Any = 1) -> dict[str, Any]:
        body = self.call(method, params, request_id)
        self.assertEqual(body["id"], request_id)
        self.assertIn("error", body, body)
        self.assertEqual(body["error"]["code"], code, body)
        error: dict[str, Any] = body["error"]
        return error

    def open_stream(self, size: int = 8) -> str:
        sid: str = self.ok("queens.open", {"size": size})["stream_id"]
        return sid
