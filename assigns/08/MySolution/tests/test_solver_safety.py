"""Required test 1: queen safety checks, run in LAMBDA3.

Rows are never shared: the board stores one column per row, so ``place``
always fills the next row (test_one_queen_per_row_by_construction). The
"same row" conflict of the reference eight_queens.lam, which stores one row
per column, is the same-column conflict in our orientation.
"""

from __future__ import annotations

import unittest

from _support import ApplyCounter, lam_eval, lam_list
from queens_rpc import solver as S  # noqa: E402 (after _support sets sys.path)


def attacks(column: int, distance: int, other: int) -> bool:
    value = lam_eval(f"attacks({column}, {distance}, {other})")
    result: bool = value.arg1
    return result


def check_safe(column: int, rows: list[int]) -> bool:
    """CPS check_safe with Boolean continuations (it is polymorphic in R)."""
    value = lam_eval(
        f"check_safe({column}, 1, {lam_list(rows)}, lam (u: unit) => true, lam (u: unit) => false)")
    result: bool = value.arg1
    return result


class AttacksPredicateTests(unittest.TestCase):
    def test_same_column(self) -> None:
        self.assertTrue(attacks(3, 1, 3))
        self.assertTrue(attacks(3, 5, 3))

    def test_diagonal_down_left(self) -> None:
        self.assertTrue(attacks(3, 2, 1))   # earlier queen two rows up, two columns left

    def test_diagonal_down_right(self) -> None:
        self.assertTrue(attacks(3, 2, 5))   # two rows up, two columns right

    def test_safe_placements(self) -> None:
        self.assertFalse(attacks(3, 1, 5))   # knight's move
        self.assertFalse(attacks(0, 3, 7))
        self.assertFalse(attacks(4, 2, 3))


class CpsSafetyCheckTests(unittest.TestCase):
    def test_empty_board_is_safe(self) -> None:
        self.assertTrue(check_safe(0, []))

    def test_same_column_conflict(self) -> None:
        self.assertFalse(check_safe(2, [2, 0]))   # row 0 has column 2

    def test_both_diagonal_directions(self) -> None:
        self.assertFalse(check_safe(1, [0]))          # up-left neighbour
        self.assertFalse(check_safe(1, [2]))          # up-right neighbour
        self.assertFalse(check_safe(3, [0, 5, 7]))    # row 0, distance 3, up-left
        self.assertFalse(check_safe(0, [3, 6, 7]))    # row 0, distance 3, up-right

    def test_safe_placement(self) -> None:
        self.assertTrue(check_safe(1, [0, 4, 7, 5, 2, 6]))   # from solution 0 4 7 5 2 6 1 3
        self.assertTrue(check_safe(3, [0, 4, 7, 5, 2, 6, 1]))

    def test_one_queen_per_row_by_construction(self) -> None:
        board = lam_eval(f"place(6, {lam_list([1, 3])})")
        self.assertEqual(S.board_rows(board), [1, 3, 6])

    def test_calls_exactly_one_continuation(self) -> None:
        # The continuation that must NOT run divides by zero when called.
        boom = "lam (u: unit) => 1 / 0"
        self.assertEqual(lam_eval(
            f"check_safe(2, 1, {lam_list([2])}, {boom}, lam (u: unit) => 7)").arg1, 7)
        self.assertEqual(lam_eval(
            f"check_safe(0, 1, {lam_list([2])}, lam (u: unit) => 9, {boom})").arg1, 9)

    def test_stops_at_first_conflict(self) -> None:
        # Nearest row (row 3, column 4) attacks column 3 diagonally, so the
        # three rows above it are never examined.
        with ApplyCounter() as count:
            self.assertFalse(check_safe(3, [0, 7, 1, 4]))
        self.assertEqual(count["attacks"], 1)
        with ApplyCounter() as count:
            self.assertTrue(check_safe(3, [2, 5, 7, 0]))
        self.assertEqual(count["attacks"], 4)


if __name__ == "__main__":
    unittest.main()
