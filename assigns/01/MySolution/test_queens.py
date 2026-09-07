#!/usr/bin/env python3
"""
test_queens.py -- test driver for the top-level functions of eight_queens.py.

This is a line-for-line mirror of [test_queens.dats]: same test order, same
case names, same "## " output format.  That is deliberate -- run_tests.sh
diffs the two drivers' stdout against each other, so any behavioural
divergence between the ATS original and this translation shows up as a diff
rather than having to be noticed by hand.

Run: python3 test_queens.py
"""

import sys
import threading

import importlib
import os

# Which implementation to exercise.  Defaults to the recursive translation;
# set QUEENS_MODULE=eight_queens_loop to run the same 42 cases against the
# iterative variant.  The expected values are properties of the algorithm,
# not of either encoding, so both must produce identical output.
q = importlib.import_module(os.environ.get("QUEENS_MODULE", "eight_queens"))
board_get = q.board_get
board_set = q.board_set
safety_test1 = q.safety_test1
safety_test2 = q.safety_test2
search = q.search

# (ntest, nfail) -- threaded through, exactly as the ATS driver does it.
stat = tuple


def b2i(b: bool) -> int:
    """ATS prints true/false, Python prints True/False.  Never print a raw
    bool, or the two drivers' output can never be diffed."""
    return 1 if b else 0


def print_int8(bd) -> None:
    """[fprint_tup] only covers arities 2-4 in ATS, so the ATS driver hand
    rolls this.  str(tuple) would insert spaces, so mirror it exactly."""
    print("(%d,%d,%d,%d,%d,%d,%d,%d)" % bd, end="")


def board_eq(a, b) -> bool:
    return (a[0] == b[0] and a[1] == b[1] and a[2] == b[2] and a[3] == b[3]
            and a[4] == b[4] and a[5] == b[5] and a[6] == b[6] and a[7] == b[7])


def assert_eq_int(st, name: str, expected: int, actual: int):
    if expected == actual:
        print("## PASS %s = %d" % (name, actual))
        return (st[0] + 1, st[1])
    print("## FAIL %s: expected %d, got %d" % (name, expected, actual))
    return (st[0] + 1, st[1] + 1)


def assert_eq_bool(st, name: str, expected: bool, actual: bool):
    return assert_eq_int(st, name, b2i(expected), b2i(actual))


def assert_eq_board(st, name: str, expected, actual):
    if board_eq(expected, actual):
        print("## PASS %s = " % name, end=""); print_int8(actual); print("")
        return (st[0] + 1, st[1])
    print("## FAIL %s: expected " % name, end=""); print_int8(expected)
    print(", got ", end=""); print_int8(actual); print("")
    return (st[0] + 1, st[1] + 1)


BDID = (0, 1, 2, 3, 4, 5, 6, 7)   # identity board, for indexing tests
BDZ = (0, 0, 0, 0, 0, 0, 0, 0)    # the seed board used by main0


# T1: board_get -- normal indices
def test_board_get_normal(st):
    bd = BDID
    st = assert_eq_int(st, "board_get/0", 0, board_get(bd, 0))
    st = assert_eq_int(st, "board_get/3", 3, board_get(bd, 3))
    st = assert_eq_int(st, "board_get/7", 7, board_get(bd, 7))
    return st


# T2: board_get -- out of range yields the ~1 sentinel
def test_board_get_range(st):
    bd = BDID
    st = assert_eq_int(st, "board_get/neg1", -1, board_get(bd, -1))
    st = assert_eq_int(st, "board_get/8", -1, board_get(bd, 8))
    st = assert_eq_int(st, "board_get/99", -1, board_get(bd, 99))
    return st


# T3: board_set -- normal update, other rows undisturbed
def test_board_set_normal(st):
    bd = BDZ
    st = assert_eq_board(st, "board_set/0", (9,0,0,0,0,0,0,0), board_set(bd, 0, 9))
    st = assert_eq_board(st, "board_set/7", (0,0,0,0,0,0,0,9), board_set(bd, 7, 9))
    st = assert_eq_board(st, "board_set/mid", (0,1,2,9,4,5,6,7), board_set(BDID, 3, 9))
    return st


# T4: board_set -- out of range is a SILENT no-op
def test_board_set_range(st):
    bd = BDID
    st = assert_eq_board(st, "board_set/neg1", bd, board_set(bd, -1, 9))
    st = assert_eq_board(st, "board_set/8", bd, board_set(bd, 8, 9))
    return st


# T5: safety_test1 -- the three conflicts, plus the safe case
def test_safety_test1(st):
    st = assert_eq_bool(st, "st1/safe", True, safety_test1(0, 0, 1, 2))
    st = assert_eq_bool(st, "st1/samecol", False, safety_test1(0, 3, 5, 3))
    st = assert_eq_bool(st, "st1/diag", False, safety_test1(0, 0, 3, 3))
    st = assert_eq_bool(st, "st1/antidiag", False, safety_test1(0, 3, 3, 0))
    # A queen is not "safe" from itself: [j0 != j1] fails.
    st = assert_eq_bool(st, "st1/self", False, safety_test1(3, 3, 3, 3))
    # Same row is never tested -- one queen per row is structural.
    st = assert_eq_bool(st, "st1/samerow", True, safety_test1(4, 0, 4, 2))
    return st


# T6: safety_test2 -- empty-prefix base case and short-circuiting
def test_safety_test2(st):
    bd = (0, 4, 7, 5, 2, 6, 1, 3)  # solution #1
    st = assert_eq_bool(st, "st2/empty", True, safety_test2(0, 0, bd, -1))
    st = assert_eq_bool(st, "st2/deepneg", True, safety_test2(0, 0, bd, -5))
    # Row 3 of solution #1 is column 5; (4,5) shares that column.
    st = assert_eq_bool(st, "st2/conflict", False, safety_test2(4, 5, bd, 3))
    st = assert_eq_bool(st, "st2/ok", True, safety_test2(4, 2, bd, 3))
    return st


# T7: search -- the whole puzzle, and j >= N with no room to backtrack
def test_search_basic(st):
    st = assert_eq_int(st, "search/total", 92, search(BDZ, 0, 0, 0))
    st = assert_eq_int(st, "search/jN", 0, search(BDZ, 0, 8, 0))
    st = assert_eq_int(st, "search/jbig", 0, search(BDZ, 0, 99, 0))
    return st


# T8: nsol is a pure pass-through accumulator
def test_search_accum(st):
    st = assert_eq_int(st, "search/seed5", 97, search(BDZ, 0, 0, 5))
    st = assert_eq_int(st, "search/seed100", 192, search(BDZ, 0, 0, 100))
    return st


# T9: seeding row 0 and resuming at row 1.  The backtrack branch has no
# floor, so this counts every solution whose row-0 queen is in column >= c,
# NOT completions of the prefix.  Differences are the per-column counts
# 4,8,16,18,18,16,8,4 -- an oracle independent of the program itself.
def test_search_resume(st):
    def seed(c):
        return search(board_set(BDZ, 0, c), 1, 0, 0)
    st = assert_eq_int(st, "search/col0", 92, seed(0))
    st = assert_eq_int(st, "search/col1", 88, seed(1))
    st = assert_eq_int(st, "search/col2", 80, seed(2))
    st = assert_eq_int(st, "search/col3", 64, seed(3))
    st = assert_eq_int(st, "search/col4", 46, seed(4))
    st = assert_eq_int(st, "search/col5", 28, seed(5))
    st = assert_eq_int(st, "search/col6", 12, seed(6))
    st = assert_eq_int(st, "search/col7", 4, seed(7))
    st = assert_eq_int(st, "search/diff0", 4, seed(0) - seed(1))
    st = assert_eq_int(st, "search/diff3", 18, seed(3) - seed(4))
    st = assert_eq_int(st, "search/mirror0", 0, (seed(0) - seed(1)) - seed(7))
    st = assert_eq_int(st, "search/mirror1", 0,
                       (seed(1) - seed(2)) - (seed(6) - seed(7)))
    st = assert_eq_int(st, "search/mirror3", 0,
                       (seed(3) - seed(4)) - (seed(4) - seed(5)))
    return st


# T10: CHARACTERIZATION of a defect.  search never re-validates the rows it
# is handed, so an illegal prefix produces fabricated "solutions".
def test_search_badprefix(st):
    st = assert_eq_int(st, "search/badprefix01", 96,
                       search((0, 1, 0, 0, 0, 0, 0, 0), 2, 0, 0))
    st = assert_eq_int(st, "search/badprefix00", 98,
                       search((0, 0, 0, 0, 0, 0, 0, 0), 2, 0, 0))
    return st


# T11: i >= N is unguarded.  i = 8 returns a nonsense count; i = 9 does not
# terminate and is therefore NOT exercised here (see TEST-RESULTS.md).
def test_search_bigrow(st):
    st = assert_eq_int(st, "search/i8", 101, search(BDZ, 8, 0, 0))
    return st


RC = 0


def run_all() -> None:
    global RC
    st = (0, 0)
    st = test_board_get_normal(st)
    st = test_board_get_range(st)
    st = test_board_set_normal(st)
    st = test_board_set_range(st)
    st = test_safety_test1(st)
    st = test_safety_test2(st)
    st = test_search_basic(st)
    st = test_search_accum(st)
    st = test_search_resume(st)
    st = test_search_badprefix(st)
    st = test_search_bigrow(st)
    print("## TOTAL %d tests, %d failure(s)" % st)
    RC = 1 if st[1] else 0


if __name__ == "__main__":
    # The seeded [search] cases recurse just as deeply as main0 does, so the
    # driver needs the same big-stack thread the program itself uses.
    sys.setrecursionlimit(1 << 16)
    threading.stack_size(64 * 1024 * 1024)
    t = threading.Thread(target=run_all)
    t.start()
    t.join()
    sys.exit(RC)
#
# end of [test_queens.py]
