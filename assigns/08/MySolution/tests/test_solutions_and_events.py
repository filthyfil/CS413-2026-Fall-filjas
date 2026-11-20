"""Required tests 3 and 4: exhaustive deterministic solutions, and every
event kind with the correct coordinates and board snapshot.

All traces come from the LAMBDA3 solver through the adapter. They are
compared with ``reference_trace``, an independent direct-style Python model
of the spec's event sequence.
"""

from __future__ import annotations

import unittest
from typing import Any

from _support import full_trace, reference_solutions, reference_trace, slow

KNOWN_COUNTS = {1: 1, 2: 0, 3: 0, 4: 2, 5: 10, 6: 4, 7: 40, 8: 92}


def solutions(trace: Any) -> list[tuple[int, ...]]:
    return [tuple(e["board"]) for e in trace if e["event"] == "solution"]


def safe_board(board: list[int]) -> bool:
    return all(board[i] != board[j] and abs(board[i] - board[j]) != j - i
               for i in range(len(board)) for j in range(i + 1, len(board)))


class SmallBoardTests(unittest.TestCase):
    def test_solution_counts_sizes_1_to_7(self) -> None:
        for n in range(1, 8):
            with self.subTest(n=n):
                self.assertEqual(len(solutions(full_trace(n))), KNOWN_COUNTS[n])

    def test_full_trace_matches_reference_model_sizes_4_to_6(self) -> None:
        for n in (4, 5, 6):
            with self.subTest(n=n):
                self.assertEqual(list(full_trace(n)), reference_trace(n))


@slow
class EightByEightTests(unittest.TestCase):
    trace: tuple[dict[str, Any], ...]

    @classmethod
    def setUpClass(cls) -> None:
        cls.trace = full_trace(8)   # ~30 s, shared by every test in this class

    def test_exactly_92_solutions(self) -> None:
        self.assertEqual(len(solutions(self.trace)), 92)

    def test_no_duplicates_and_all_valid(self) -> None:
        sols = solutions(self.trace)
        self.assertEqual(len(set(sols)), 92)
        for board in sols:
            self.assertEqual(len(board), 8)
            self.assertTrue(safe_board(list(board)), board)

    def test_deterministic_depth_first_order(self) -> None:
        sols = solutions(self.trace)
        # Left-to-right DFS yields boards in lexicographic order...
        self.assertEqual(sols, sorted(sols))
        self.assertEqual(sols[0], (0, 4, 7, 5, 2, 6, 1, 3))
        self.assertEqual(sols[-1], (7, 3, 0, 2, 5, 1, 6, 4))
        # ...and the same order as the independent reference search.
        self.assertEqual(sols, reference_solutions(8))

    def test_full_trace_matches_reference_model(self) -> None:
        self.assertEqual(list(self.trace), reference_trace(8))

    def test_event_totals(self) -> None:
        counts: dict[str, int] = {}
        for e in self.trace:
            counts[e["event"]] = counts.get(e["event"], 0) + 1
        self.assertEqual(counts, {"try": 15720, "place": 2056, "reject": 13664,
                                  "backtrack": 2056, "solution": 92, "done": 1})

    def test_done_exactly_once_and_last(self) -> None:
        done = [i for i, e in enumerate(self.trace) if e["event"] == "done"]
        self.assertEqual(done, [len(self.trace) - 1])
        self.assertEqual(self.trace[-1], {"event": "done"})

    def test_event_schema_and_snapshots(self) -> None:
        check_event_invariants(self, self.trace, 8)


def check_event_invariants(tc: unittest.TestCase, trace: Any, n: int) -> None:
    """Replay the trace with an explicit stack and check each event's data."""
    stack: list[int] = []          # the partial board implied by events so far
    pending_try: tuple[int, int] | None = None
    seen = set()
    for e in trace:
        kind = e["event"]
        seen.add(kind)
        if kind in ("try", "place", "reject", "backtrack"):
            tc.assertEqual(set(e), {"event", "column", "row", "board"}, e)
            tc.assertTrue(0 <= e["column"] < n and 0 <= e["row"] < n, e)
        if kind == "try":
            tc.assertIsNone(pending_try)
            tc.assertEqual(e["board"], stack)                 # current partial board
            tc.assertEqual(e["row"], len(stack))              # next row to fill
            pending_try = (e["column"], e["row"])
        elif kind in ("place", "reject"):
            tc.assertEqual((e["column"], e["row"]), pending_try)   # answers the last try
            pending_try = None
            if kind == "place":
                tc.assertEqual(e["board"], stack + [e["column"]])  # updated board
                tc.assertTrue(safe_board(e["board"]))
                stack = e["board"]
            else:
                tc.assertEqual(e["board"], stack)                  # unchanged board
                tc.assertFalse(safe_board(stack + [e["column"]]))  # really conflicts
        elif kind == "backtrack":
            tc.assertIsNone(pending_try)
            tc.assertEqual(stack[-1], e["column"])                 # removes the last queen
            tc.assertEqual(e["row"], len(stack) - 1)
            tc.assertEqual(e["board"], stack[:-1])                 # restored board
            stack = e["board"]
        elif kind == "solution":
            tc.assertEqual(set(e), {"event", "board"})
            tc.assertEqual(e["board"], stack)
            tc.assertEqual(len(stack), n)
        elif kind == "done":
            tc.assertEqual(e, {"event": "done"})
            tc.assertEqual(stack, [])
    tc.assertEqual(seen, {"try", "place", "reject", "backtrack", "solution", "done"})


class EventKindTests(unittest.TestCase):
    def test_each_kind_with_coordinates_and_snapshot_4x4(self) -> None:
        trace = full_trace(4)
        check_event_invariants(self, trace, 4)
        self.assertEqual(trace[:4], (
            {"event": "try", "column": 0, "row": 0, "board": []},
            {"event": "place", "column": 0, "row": 0, "board": [0]},
            {"event": "try", "column": 0, "row": 1, "board": [0]},
            {"event": "reject", "column": 0, "row": 1, "board": [0]},
        ))
        first_backtrack = next(e for e in trace if e["event"] == "backtrack")
        self.assertEqual(first_backtrack, {"event": "backtrack", "column": 2, "row": 1, "board": [0]})
        self.assertEqual([e for e in trace if e["event"] == "solution"],
                         [{"event": "solution", "board": [1, 3, 0, 2]},
                          {"event": "solution", "board": [2, 0, 3, 1]}])


if __name__ == "__main__":
    unittest.main()
