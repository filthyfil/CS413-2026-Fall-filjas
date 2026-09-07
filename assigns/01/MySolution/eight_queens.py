#!/usr/bin/env python3
"""
The Eight-Queens puzzle -- a hand transliteration of [eight_queens.dats].

The ATS original is at:
  https://ats-lang.github.io/FROZEN000/DOCUMENT/INT2PROGINATS/HTML/
  INT2PROGINATS-BOOK-onechunk.html#example-the-eight-queens-puzzle

Design decisions carried over verbatim from the ATS source:
  * the board is an immutable 8-tuple ([int8]), index = row, value = column;
  * every function keeps its ATS name, parameter list and return value;
  * [board_get] / [board_set] keep their if-chains (ATS cannot project a
    tuple at a runtime index, and [board_set] rebuilds rather than mutates);
  * [safety_test2] and [search] stay recursive;
  * the printed output is byte-for-byte identical to the ATS program.

Run: python3 eight_queens.py
"""

import sys
import threading

N = 8

# typedef int8 = (int, int, int, int, int, int, int, int)
int8 = tuple  # an 8-tuple of ints


def print_dots(i: int) -> None:
    if i > 0:
        print(". ", end="")
        print_dots(i - 1)
    else:
        pass
# end of [print_dots]


def print_row(i: int) -> None:
    print_dots(i)
    print("Q ", end="")
    print_dots(N - i - 1)
    print("\n", end="")
# end of [print_row]


def print_board(bd: int8) -> None:
    print_row(bd[0]); print_row(bd[1]); print_row(bd[2]); print_row(bd[3])
    print_row(bd[4]); print_row(bd[5]); print_row(bd[6]); print_row(bd[7])
    print_newline()
# end of [print_board]


def print_newline() -> None:
    print("\n", end="")
# end of [print_newline]


def board_get(bd: int8, i: int) -> int:
    if i == 0:
        return bd[0]
    elif i == 1:
        return bd[1]
    elif i == 2:
        return bd[2]
    elif i == 3:
        return bd[3]
    elif i == 4:
        return bd[4]
    elif i == 5:
        return bd[5]
    elif i == 6:
        return bd[6]
    elif i == 7:
        return bd[7]
    else:
        return -1  # [~1] in ATS
# end of [board_get]


def board_set(bd: int8, i: int, j: int) -> int8:
    (x0, x1, x2, x3, x4, x5, x6, x7) = bd
    if i == 0:
        x0 = j; return (x0, x1, x2, x3, x4, x5, x6, x7)
    elif i == 1:
        x1 = j; return (x0, x1, x2, x3, x4, x5, x6, x7)
    elif i == 2:
        x2 = j; return (x0, x1, x2, x3, x4, x5, x6, x7)
    elif i == 3:
        x3 = j; return (x0, x1, x2, x3, x4, x5, x6, x7)
    elif i == 4:
        x4 = j; return (x0, x1, x2, x3, x4, x5, x6, x7)
    elif i == 5:
        x5 = j; return (x0, x1, x2, x3, x4, x5, x6, x7)
    elif i == 6:
        x6 = j; return (x0, x1, x2, x3, x4, x5, x6, x7)
    elif i == 7:
        x7 = j; return (x0, x1, x2, x3, x4, x5, x6, x7)
    else:
        return bd
# end of [board_set]


def safety_test1(i0: int, j0: int, i1: int, j1: int) -> bool:
    #
    # [abs]: the absolute value function
    #
    return j0 != j1 and abs(i0 - i1) != abs(j0 - j1)
# end of [safety_test1]


def safety_test2(i0: int, j0: int, bd: int8, i: int) -> bool:
    if i >= 0:
        if safety_test1(i0, j0, i, board_get(bd, i)):
            return safety_test2(i0, j0, bd, i - 1)
        else:
            return False
    else:
        return True
# end of [safety_test2]


def search(bd: int8, i: int, j: int, nsol: int) -> int:
    #
    if j < N:
        test = safety_test2(i, j, bd, i - 1)
        if test:
            bd1 = board_set(bd, i, j)
            if i + 1 == N:
                print("Solution #", nsol + 1, ":\n\n", sep="", end="")
                print_board(bd1)
                return search(bd, i, j + 1, nsol + 1)
            # end of [then]
            else:
                return search(bd1, i + 1, 0, nsol)  # positioning next piece
            # end of [if]
        # end of [then]
        else:
            return search(bd, i, j + 1, nsol)
        # end of [if]
    # end of [then]
    else:
        if i > 0:
            return search(bd, i - 1, board_get(bd, i - 1) + 1, nsol)
        else:
            return nsol
        # end of [if]
    # end of [else]
    #
# end of [search]


def main0() -> None:
    #
    bd0: int8 = (0, 0, 0, 0, 0, 0, 0, 0)
    nsol = search(bd0, 0, 0, 0)  # (bd, i, j, nsol)
    #
    print("The total number of solutions is ", nsol, ".\n", sep="", end="")
# end of [main0]


if __name__ == "__main__":
    #
    # [search] is tail-recursive in ATS, where the call is a jump and costs
    # no stack.  Python has no tail-call elimination, so the 17685 calls the
    # 8x8 search performs become 17685 live frames.  Rather than rewrite
    # [search] as a loop -- which would lose the structure of the original --
    # give the interpreter a stack deep enough to run the translation as
    # written.

    sys.setrecursionlimit(1 << 16)
    threading.stack_size(64 * 1024 * 1024)
    thr = threading.Thread(target=main0)
    thr.start()
    thr.join()
#
# end of [eight_queens.py]
