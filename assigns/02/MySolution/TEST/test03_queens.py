"""Tests for the LAMBDA0 translation of the eight-queens program.

Run with: python3 TEST/test03_queens.py
Requires Python 3.12 or later, like lambda0.py.

The 8x8 tests use the tree-recursive search (queens_tree_term): the
line-for-line search needs several GB of memory on an 8x8 board in this
interpreter.  The 8x8 search runs once (about 6 minutes) and its result is
shared by every test that needs it.  Set QUEENS_SKIP_FULL=1 to skip those
tests and run only the fast ones; set QUEENS_ATS_FULL=1 on a machine with
enough memory to also run the line-for-line search on 8x8.
"""

import os
import subprocess
import sys
import unittest
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
MYSOLUTION = HERE.parent
sys.path.insert(0, str(MYSOLUTION))

from lambda0 import T0Mint, T0Mbtf, T0Mapp, T0Mpair, t0erm_fvset, t0erm_size
from queens_lambda0 import (
    N, ABS, SAFETY_TEST1,
    board_get_term, board_set_term, board_pack_term, safety_test2_term,
    search_term, search_tree_term, queens_term, queens_tree_term,
    board_term, board_from_term, solve, evaluate, format_output,
)

# Number of solutions for n = 0, 1, ..., 8 (OEIS A000170).
SOLUTION_COUNTS = [1, 1, 0, 0, 2, 10, 4, 40, 92]

ATS_SOURCE = MYSOLUTION / "eight_queens.dats"
ATS_OUTPUT_COPY = MYSOLUTION / "output_ats.txt"


def apply(f, *args):
    """f a b c  as nested T0Mapp (for the curried board helpers)."""
    for a in args:
        f = T0Mapp(f, a)
    return f


def tup(*terms):
    """(a, b, c) as right-nested T0Mpair (for the tupled recursive functions)."""
    *init, last = terms
    for t in reversed(init):
        last = T0Mpair(t, last)
    return last


def is_valid_solution(board, n):
    """Eight queens, no two sharing a row, column or diagonal."""
    if len(board) != n or any(not 0 <= c < n for c in board):
        return False
    for i0 in range(n):
        for i1 in range(i0 + 1, n):
            if board[i0] == board[i1] or abs(i0 - i1) == abs(board[i0] - board[i1]):
                return False
    return True


@lru_cache(maxsize=None)
def solve_cached(n, program=queens_term):
    return solve(n, program)


def ats_output():
    """The original program's output: run it if it can be built, else use the copy."""
    # patscc writes eight_queens_dats.c into the current directory; build in
    # TEST/ and remove both it and the executable afterwards.
    exe = HERE / "eight_queens_ats"
    try:
        subprocess.run(["patscc", "-DATS_MEMALLOC_LIBC", "-o", str(exe), str(ATS_SOURCE)],
                       check=True, capture_output=True, cwd=str(HERE))
        try:
            return subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout
        finally:
            for leftover in (exe, HERE / "eight_queens_dats.c"):
                leftover.unlink(missing_ok=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ATS_OUTPUT_COPY.read_text()


def parse_ats_output(text):
    """Extract (nsol, boards) from the ATS program's printed output."""
    boards, current = [], []
    for line in text.splitlines():
        if line.startswith("Q") or line.startswith("."):
            current.append(line.split().index("Q"))
            if len(current) == N:
                boards.append(tuple(current))
                current = []
    nsol = int(text.rsplit("is ", 1)[1].rstrip(".\n"))
    return nsol, boards


class TestHelpers(unittest.TestCase):
    def test_terms_are_closed(self):
        for term in (ABS, SAFETY_TEST1, board_get_term(), board_set_term(),
                     board_pack_term(), safety_test2_term(), search_term(), queens_term(),
                     search_tree_term(), queens_tree_term()):
            with self.subTest(term=type(term).__name__):
                self.assertEqual(t0erm_fvset(term), frozenset())

    def test_abs(self):
        for x, expected in [(0, 0), (5, 5), (-5, 5)]:
            self.assertEqual(evaluate(T0Mapp(ABS, T0Mint(x))), T0Mint(expected))

    def test_board_roundtrip(self):
        board = (0, 4, 7, 5, 2, 6, 1, 3)
        self.assertEqual(board_from_term(board_term(board)), board)

    def test_board_get(self):
        board = (3, 1, 4, 1, 5, 9, 2, 6)
        for i in range(N):
            with self.subTest(i=i):
                term = apply(board_get_term(), board_term(board), T0Mint(i))
                self.assertEqual(evaluate(term), T0Mint(board[i]))
        # Out of range gives ~1, as in the ATS source.
        self.assertEqual(evaluate(apply(board_get_term(), board_term(board), T0Mint(8))), T0Mint(-1))

    def test_board_set(self):
        board = (0,) * N
        for i in range(N):
            with self.subTest(i=i):
                term = apply(board_set_term(), board_term(board), T0Mint(i), T0Mint(7))
                expected = tuple(7 if k == i else 0 for k in range(N))
                self.assertEqual(board_from_term(evaluate(term)), expected)
        # Out of range leaves the board unchanged, as in the ATS source.
        term = apply(board_set_term(), board_term(board), T0Mint(8), T0Mint(7))
        self.assertEqual(board_from_term(evaluate(term)), board)

    def test_board_set_evaluates_to_a_pair_value(self):
        # A board is an N-tuple of pairs whose leaves are integers.
        value = evaluate(apply(board_set_term(4), board_term((0, 0, 0, 0)), T0Mint(1), T0Mint(2)))
        self.assertEqual(value, T0Mpair(T0Mint(0), T0Mpair(T0Mint(2), T0Mpair(T0Mint(0), T0Mint(0)))))

    def test_board_pack(self):
        board = (0, 4, 7, 5, 2, 6, 1, 3)
        packed = sum(c * N ** k for k, c in enumerate(board))
        self.assertEqual(evaluate(T0Mapp(board_pack_term(), board_term(board))), T0Mint(packed))


class TestConflictChecks(unittest.TestCase):
    def check1(self, i0, j0, i1, j1):
        return evaluate(apply(SAFETY_TEST1, T0Mint(i0), T0Mint(j0), T0Mint(i1), T0Mint(j1)))

    def test_safety_test1(self):
        cases = [
            ((0, 0, 1, 0), False),   # same column
            ((0, 0, 1, 1), False),   # diagonal
            ((0, 3, 2, 1), False),   # anti-diagonal
            ((0, 0, 1, 2), True),    # knight's move: safe
            ((5, 2, 1, 7), True),
            ((3, 6, 7, 2), False),   # |3-7| == |6-2|
        ]
        for args, expected in cases:
            with self.subTest(args=args):
                self.assertEqual(self.check1(*args), T0Mbtf(expected))

    def test_safety_test1_matches_python(self):
        n = 4
        for i0 in range(n):
            for j0 in range(n):
                for i1 in range(n):
                    for j1 in range(n):
                        expected = j0 != j1 and abs(i0 - i1) != abs(j0 - j1)
                        self.assertEqual(self.check1(i0, j0, i1, j1), T0Mbtf(expected))

    def test_safety_test2(self):
        # Rows 0..2 hold queens at columns 0, 4, 7 (start of the first solution).
        board = board_term((0, 4, 7, 0, 0, 0, 0, 0))
        def check2(i0, j0):
            return evaluate(T0Mapp(safety_test2_term(), tup(T0Mint(i0), T0Mint(j0), board, T0Mint(i0 - 1))))
        self.assertEqual(check2(3, 5), T0Mbtf(True))    # the actual next queen
        self.assertEqual(check2(3, 4), T0Mbtf(False))   # column clash with row 1
        self.assertEqual(check2(3, 3), T0Mbtf(False))   # diagonal from (0, 0)
        self.assertEqual(check2(3, 6), T0Mbtf(False))   # diagonal from (2, 7)
        # i = -1: nothing to check, always safe.
        self.assertEqual(evaluate(T0Mapp(safety_test2_term(), tup(T0Mint(0), T0Mint(0), board, T0Mint(-1)))),
                         T0Mbtf(True))


class TestSmallBoards(unittest.TestCase):
    def test_solution_counts(self):
        for n in range(1, 7):
            with self.subTest(n=n):
                nsol, boards = solve_cached(n)
                self.assertEqual(nsol, SOLUTION_COUNTS[n])
                self.assertEqual(len(boards), nsol)

    def test_solutions_are_valid_and_distinct(self):
        for n in (4, 5, 6):
            with self.subTest(n=n):
                _, boards = solve_cached(n)
                for board in boards:
                    self.assertTrue(is_valid_solution(board, n), board)
                self.assertEqual(len(set(boards)), len(boards))

    def test_four_queens(self):
        # Row-by-row, column-ascending search finds these two, in this order.
        self.assertEqual(solve_cached(4), (2, [(1, 3, 0, 2), (2, 0, 3, 1)]))

    def test_search_returns_pair_of_count_and_packed_boards(self):
        first, second = (1, 3, 0, 2), (2, 0, 3, 1)
        pack = lambda b: sum(c * 4 ** k for k, c in enumerate(b))
        for program in (queens_term, queens_tree_term):
            with self.subTest(program=program.__name__):
                value = evaluate(program(4))
                self.assertIsInstance(value, T0Mpair)
                self.assertEqual(value.arg1, T0Mint(2))
                self.assertEqual(value.arg2, T0Mint(pack(first) * 4 ** 4 + pack(second)))

    def test_tree_search_agrees_with_ats_form(self):
        # The line-for-line translation of the ATS `search` and the
        # tree-recursive one find the same boards in the same order.
        for n in range(1, 6):
            with self.subTest(n=n):
                self.assertEqual(solve_cached(n), solve_cached(n, queens_tree_term))

    def test_search_terms_are_the_same_size_order(self):
        # Sanity check that the restructuring did not balloon the term.
        self.assertLess(t0erm_size(search_tree_term()), t0erm_size(search_term()))


@unittest.skipIf(os.environ.get("QUEENS_SKIP_FULL"), "QUEENS_SKIP_FULL is set")
class TestEightQueens(unittest.TestCase):
    # Uses the tree-recursive search; see the module docstring.
    def test_count(self):
        nsol, boards = solve_cached(N, queens_tree_term)
        self.assertEqual(nsol, 92)
        self.assertEqual(len(boards), 92)

    def test_all_solutions_valid_and_distinct(self):
        _, boards = solve_cached(N, queens_tree_term)
        for board in boards:
            self.assertTrue(is_valid_solution(board, N), board)
        self.assertEqual(len(set(boards)), 92)

    def test_first_solution(self):
        _, boards = solve_cached(N, queens_tree_term)
        self.assertEqual(boards[0], (0, 4, 7, 5, 2, 6, 1, 3))

    def test_matches_ats_program(self):
        # Same count, same boards, in the same order, and identical printed output.
        text = ats_output()
        ats_nsol, ats_boards = parse_ats_output(text)
        nsol, boards = solve_cached(N, queens_tree_term)
        self.assertEqual((nsol, boards), (ats_nsol, ats_boards))
        self.assertEqual(format_output(nsol, boards), text)

    @unittest.skipUnless(os.environ.get("QUEENS_ATS_FULL"), "needs several GB; set QUEENS_ATS_FULL=1")
    def test_line_for_line_search_matches_on_8x8(self):
        self.assertEqual(solve_cached(N, queens_term), solve_cached(N, queens_tree_term))


if __name__ == "__main__":
    unittest.main(verbosity=2)
