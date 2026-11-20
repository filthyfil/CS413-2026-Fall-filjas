"""Required test 2: CPS success and failure paths, including resumption.

These call the LAMBDA3 ``search`` with test continuations that emit marker
events: kind 8 for "success continuation called" (carrying the board) and
kind 7 for "failure continuation called". That shows which continuation the
solver hands control to, and when.
"""

from __future__ import annotations

import unittest

from _support import E, lam_eval, lam_list, raw_events

SUCCESS, FAILURE = 8, 7
ON_SUCCESS = f"lam (p: (List[sint], unit -> Strm[{E}])) => emit((8, 0 - 1, 0 - 1, p.0), p.1)"
ON_FAILURE = ("lam (u: unit) => emit((7, 0 - 1, 0 - 1, list_nil()), "
              "lam (v: unit) => lazy_make(lam (w: unit) => stcn_nil()))")
TRY, PLACE, REJECT, BACKTRACK = 0, 1, 2, 3


def search(size: int, rows: list[int]) -> list[tuple[int, int, int, list[int]]]:
    strm = lam_eval(f"search({size}, {len(rows)}, {lam_list(rows)}, {ON_SUCCESS}, {ON_FAILURE})")
    return raw_events(strm)


class CpsSearchTests(unittest.TestCase):
    def test_success_receives_board_and_failure_continuation(self) -> None:
        # A complete board goes straight to the success continuation, whose
        # resume argument is exactly the failure continuation we passed in.
        self.assertEqual(search(4, [1, 3, 0, 2]),
                         [(SUCCESS, -1, -1, [1, 3, 0, 2]), (FAILURE, -1, -1, [])])

    def test_failure_when_row_has_no_safe_column(self) -> None:
        # Rows [0, 2] is a dead end on 4x4: every row-2 column is rejected,
        # then control passes to the failure continuation, and nothing else runs.
        events = search(4, [0, 2])
        self.assertEqual(events, [
            (TRY, 0, 2, [0, 2]), (REJECT, 0, 2, [0, 2]),
            (TRY, 1, 2, [0, 2]), (REJECT, 1, 2, [0, 2]),
            (TRY, 2, 2, [0, 2]), (REJECT, 2, 2, [0, 2]),
            (TRY, 3, 2, [0, 2]), (REJECT, 3, 2, [0, 2]),
            (FAILURE, -1, -1, []),
        ])

    def test_reject_resumes_at_next_column(self) -> None:
        events = search(4, [1])
        self.assertEqual(events[:3], [(TRY, 0, 1, [1]), (REJECT, 0, 1, [1]), (TRY, 1, 1, [1])])

    def test_resume_after_solution_continues_search(self) -> None:
        events = search(4, [1])
        kinds = [e[0] for e in events]
        self.assertEqual(kinds.count(SUCCESS), 1)
        i = kinds.index(SUCCESS)
        self.assertEqual(events[i], (SUCCESS, -1, -1, [1, 3, 0, 2]))
        # Resuming first undoes the last queen, then tries the next column in that row.
        self.assertEqual(events[i + 1], (BACKTRACK, 2, 3, [1, 3, 0]))
        self.assertEqual(events[i + 2], (TRY, 3, 3, [1, 3, 0]))
        # The enclosing failure continuation runs exactly once, at the very end.
        self.assertEqual(kinds.count(FAILURE), 1)
        self.assertEqual(kinds[-1], FAILURE)

    def test_backtrack_restores_board_and_tries_next_candidate(self) -> None:
        events = search(4, [0])
        for i, (kind, column, row, board) in enumerate(events):
            if kind == BACKTRACK:
                # Restored board has exactly `row` queens, and the next event
                # is the next candidate in that row, or (if the row is done)
                # an enclosing backtrack/failure.
                self.assertEqual(len(board), row)
                nxt = events[i + 1]
                if column + 1 < 4:
                    self.assertEqual(nxt, (TRY, column + 1, row, board))
                else:
                    self.assertIn(nxt[0], (BACKTRACK, FAILURE))

    def test_search_is_continuation_driven_not_wrapped(self) -> None:
        # Swapping in a different success continuation changes what the
        # stream contains at each solution. A direct-style solver wrapped
        # in CPS could not be steered this way mid-search.
        stop_at_first = "lam (p: (List[sint], unit -> Strm[" + E + "])) => " \
                        "emit((8, 0 - 1, 0 - 1, p.0), lam (u: unit) => lazy_make(lam (w: unit) => stcn_nil()))"
        strm = lam_eval(f"search(6, 0, list_nil(), {stop_at_first}, {ON_FAILURE})")
        events = raw_events(strm)
        self.assertEqual(events[-1], (SUCCESS, -1, -1, [1, 3, 5, 0, 2, 4]))
        self.assertNotIn(FAILURE, [e[0] for e in events])


if __name__ == "__main__":
    unittest.main()
