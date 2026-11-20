"""Required test 5: the event stream is genuinely lazy.

Two kinds of evidence, neither of which looks at how a value prints:

* Trace hook: ``ApplyCounter`` counts interpreter applications, in
  particular calls of the solver's ``attacks`` and ``check_safe``, which is
  exactly the search work.
* Delayed failing computations: the real solver runs with a continuation
  that divides by zero if it is ever called. Reading a prefix succeeds, so
  that continuation was never forced.
"""

from __future__ import annotations

import unittest

from _support import E, SOLVER, ApplyCounter, lam_eval, raw_events, reference_trace, unforced

BOOM_FAILURE = "lam (u: unit) => if 1 / 0 == 0 then root_exhausted() else root_exhausted()"
BOOM_SUCCESS = (f"lam (p: (List[sint], unit -> Strm[{E}])) => "
                "if 1 / 0 == 0 then on_solution(p.0, p.1) else on_solution(p.0, p.1)")


class OpeningDoesNoSearchTests(unittest.TestCase):
    def test_open_performs_no_search(self) -> None:
        with ApplyCounter() as count:
            stream = SOLVER.open(10)
        self.assertEqual(count.total, 1)            # only the call queens_events(10)
        self.assertEqual(count["attacks"], 0)
        self.assertEqual(count["try_column"], 0)
        self.assertTrue(unforced(stream))           # interpreter flag: thunk not run

    def test_constructing_with_failing_root_continuations_is_harmless(self) -> None:
        # If construction did any search, the zero division would happen here.
        lam_eval(f"lazy_make(lam (u: unit) => lazy_eval(search(8, 0, list_nil(), {BOOM_SUCCESS}, {BOOM_FAILURE})))")


class ForcingIsBoundedTests(unittest.TestCase):
    def test_forcing_one_cell_does_not_force_its_tail(self) -> None:
        stream = SOLVER.open(8)
        with ApplyCounter() as count:
            events, _ = stream.take(1)
        self.assertEqual(events, [{"event": "try", "column": 0, "row": 0, "board": []}])
        self.assertEqual(count["attacks"], 0)            # the first try needs no check yet
        self.assertEqual(count["check_safe"], 0)
        self.assertTrue(unforced(stream))                # the tail is still a suspension

    def test_bounded_prefix_leaves_later_work_unforced(self) -> None:
        stream = SOLVER.open(10)
        with ApplyCounter() as count:
            events, done = stream.take(32)
        self.assertFalse(done)
        self.assertEqual(events, reference_trace(10)[:32])
        self.assertTrue(unforced(stream))
        # 32 events need well under 100 attack checks; the full 10x10 search does millions.
        self.assertLess(count["attacks"], 100)
        self.assertEqual(stream.events_emitted, 32)

    def test_each_cell_costs_at_most_one_safety_check(self) -> None:
        # Forcing a single cell runs at most one check_safe, i.e. at most `row`
        # attack tests (< size), across a long stretch of a 10x10 search.
        stream = SOLVER.open(10)
        worst = 0
        for _ in range(1500):
            with ApplyCounter() as count:
                stream.take(1)
            worst = max(worst, count["attacks"])
            self.assertLessEqual(count["check_safe"], 10)
        self.assertLessEqual(worst, 9)

    def test_forced_cells_are_memoized(self) -> None:
        strm = SOLVER.open(6).cursor
        raw_events(strm, 50)
        with ApplyCounter() as count:
            again = raw_events(strm, 50)          # re-walk the same, already forced cells
        self.assertEqual(len(again), 50)
        self.assertEqual(count["attacks"], 0)
        self.assertEqual(count["check_safe"], 0)


class DelayedFailureTests(unittest.TestCase):
    def test_prefix_before_first_solution_never_runs_success_continuation(self) -> None:
        strm = lam_eval(f"search(8, 0, list_nil(), {BOOM_SUCCESS}, root_exhausted)")
        prefix = raw_events(strm, 200)              # the first solution is event #1858
        self.assertEqual(len(prefix), 200)
        with self.assertRaises(ZeroDivisionError):
            raw_events(strm, 3000)                  # reaching the solution forces it

    def test_unrequested_root_failure_is_never_run(self) -> None:
        strm = lam_eval(f"search(4, 0, list_nil(), on_solution, {BOOM_FAILURE})")
        n = len(reference_trace(4)) - 1             # every event except done
        self.assertEqual(len(raw_events(strm, n)), n)
        with self.assertRaises(ZeroDivisionError):
            raw_events(strm, n + 1)


if __name__ == "__main__":
    unittest.main()
