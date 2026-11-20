"""Bridge between Python and the LAMBDA3 CPS solver (solver/queens_cps.lam).

This module knows nothing about HTTP or JSON-RPC. It

* loads and type-checks the fixed, reviewed solver source once,
* opens an event stream for a board size *without forcing it*,
* forces stream cells one at a time on request, and
* converts each LAMBDA3 event tuple into a plain JSON-ready dict.

Interpreter values (closures, environments, lazy cells) never leave this
module. Callers only see ``dict``/``list``/``int``/``str`` values.

No client-supplied source text is ever evaluated. The only expressions
evaluated here are the two fixed ones parsed at import time
(``queens_events(size)`` and ``lazy_eval(s)``), with the size bound as a
LAMBDA3 integer value.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

SOLUTION_DIR = Path(__file__).resolve().parents[1]
SOLVER_SOURCE = SOLUTION_DIR / "solver" / "queens_cps.lam"
# The supplied interpreter sits next to MySolution/ (assigns/08/LAMBDA3).
LAMBDA3_DIR = Path(os.environ.get("QUEENS_LAMBDA3_DIR", SOLUTION_DIR.parent / "LAMBDA3")).resolve()

if str(LAMBDA3_DIR) not in sys.path:
    # lambda3.py does `from basics0 import ...`, so its directory must be importable.
    sys.path.insert(0, str(LAMBDA3_DIR))

import lambda3 as L  # noqa: E402
from basics0 import fnlist_cons, fnlist_nil  # noqa: E402

# Event kind codes, in the order documented in queens_cps.lam.
KINDS = ("try", "place", "reject", "backtrack", "solution", "done")
_CELL_KINDS = frozenset({"try", "place", "reject", "backtrack"})

# The only two expressions this module ever evaluates.
_OPEN_EXPR = L.d0exp_parse("queens_events(size)")
_FORCE_EXPR = L.d0exp_parse("lazy_eval(s)")

type Event = dict[str, Any]


class SolverError(RuntimeError):
    """The solver produced a value that does not match the event schema."""


# -- value conversion -----------------------------------------------------------

def _int(value: Any, what: str) -> int:
    if not isinstance(value, L.D0Vint):
        raise SolverError(f"{what}: integer expected")
    result: int = value.arg1
    return result


def board_rows(value: Any) -> list[int]:
    """Convert a LAMBDA3 board (newest row first) to columns in row order."""
    if not isinstance(value, L.D0Vlist):
        raise SolverError("board: list expected")
    columns: list[int] = []
    items = value.arg1
    while isinstance(items, fnlist_cons):
        columns.append(_int(items.arg1, "board entry"))
        items = items.arg2
    if not isinstance(items, fnlist_nil):
        raise SolverError("board: malformed list")
    columns.reverse()
    return columns


def decode_event(value: Any) -> Event:
    """Convert one ``(kind, column, row, board)`` tuple to its JSON form.

    try/place/reject/backtrack -> {"event", "column", "row", "board"}
    solution                   -> {"event": "solution", "board"}
    done                       -> {"event": "done"}
    """
    if not isinstance(value, L.D0Vtupl) or len(value.arg1) != 4:
        raise SolverError("event: 4-tuple expected")
    kind_code, column, row, board = value.arg1
    code = _int(kind_code, "event kind")
    if not 0 <= code < len(KINDS):
        raise SolverError("event: unknown kind")
    kind = KINDS[code]
    if kind in _CELL_KINDS:
        return {"event": kind, "column": _int(column, "column"),
                "row": _int(row, "row"), "board": board_rows(board)}
    if kind == "solution":
        return {"event": kind, "board": board_rows(board)}
    return {"event": kind}


# -- streams --------------------------------------------------------------------

def force(strm: Any) -> Any:
    """Force one LAMBDA3 stream cell. The interpreter memoizes lazy values,
    so forcing the same cell twice repeats no work."""
    cell = L.d0exp_evaluate(_FORCE_EXPR, L.ENVcns("s", strm, L.ENVnil()))
    if not isinstance(cell, L.D0Vstcn):
        raise SolverError("stream: constructor expected")
    return cell


class EventStream:
    """A cursor over one lazy solver stream.

    ``cursor`` is the unforced remainder: a LAMBDA3 ``Strm[Event]``.
    ``take(n)`` forces at most ``n`` cells and moves the cursor to the tail
    of the last forced cell. That tail is left unevaluated. Once ``done``
    has been produced the cursor is dropped, so an exhausted stream holds
    no interpreter state.

    Not thread-safe by itself. The stream table serializes access per stream.
    """

    def __init__(self, size: int, strm: Any):
        self.size = size
        self.cursor: Any | None = strm
        self.events_emitted = 0

    @property
    def exhausted(self) -> bool:
        return self.cursor is None

    def take(self, limit: int) -> tuple[list[Event], bool]:
        """Force up to ``limit`` events. Return ``(events, exhausted)``.

        All-or-nothing: the cursor only advances after every requested cell
        has been forced and decoded. If forcing fails partway, the stream is
        left where it was. Lazy cells are memoized, so a retry returns the
        same events without redoing search work.
        """
        if limit < 1:
            raise ValueError("limit must be positive")
        events: list[Event] = []
        cursor = self.cursor
        while cursor is not None and len(events) < limit:
            cell = force(cursor)
            if not cell.is_cons:   # defensive: the solver always ends with done
                cursor = None
                break
            event = decode_event(cell.head)
            events.append(event)
            cursor = None if event["event"] == "done" else cell.tail
        self.cursor = cursor
        self.events_emitted += len(events)
        return events, cursor is None


class QueensSolver:
    """Loads the LAMBDA3 solver once and opens independent event streams."""

    def __init__(self, source_path: Path = SOLVER_SOURCE):
        declarations = L.d0cls_parse(Path(source_path).read_text())
        L.d0cls_typecheck(declarations)
        self.declarations = declarations   # exposed for tests (trace hooks)
        # Evaluating the declarations only builds closures and does no search.
        self._queens_events = L.d0exp_evaluate(L.D0Elets(declarations, L.D0Evar("queens_events")))
        if not isinstance(self._queens_events, (L.D0Vlam, L.D0Vfix)):
            raise SolverError("queens_events must be a function")

    def open(self, size: int) -> EventStream:
        """Create a fresh stream. This performs no search: the returned
        stream's first cell is still an unevaluated suspension."""
        if isinstance(size, bool) or not isinstance(size, int) or size < 1:
            raise ValueError("size must be a positive integer")
        env = L.ENVcns("size", L.D0Vint(size),
                       L.ENVcns("queens_events", self._queens_events, L.ENVnil()))
        strm = L.d0exp_evaluate(_OPEN_EXPR, env)
        if not isinstance(strm, L.D0Vlazy):
            raise SolverError("queens_events must return a lazy stream")
        return EventStream(size, strm)
