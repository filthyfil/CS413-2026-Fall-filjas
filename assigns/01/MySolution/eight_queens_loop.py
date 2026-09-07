#!/usr/bin/env python3
"""
eight_queens_loop.py -- iterative variant of [eight_queens.py].

Same program, same output, byte for byte.  The only difference is that the
three tail-recursive functions of the ATS original -- [print_dots],
[safety_test2] and [search] -- are written as loops here instead of as
recursive calls.

Why this file exists
--------------------
ATS compiles a tail call into a jump, so [search]'s 17685 successive calls
cost no stack at all.  Python has no tail-call elimination, so the direct
transliteration in [eight_queens.py] turns those into 17685 live frames and
needs [sys.setrecursionlimit] plus a 64 MB thread to run.  That workaround
was chosen deliberately there, to keep the recursive shape of the original
visible.  This file makes the opposite trade: it gives up the shape in order
to run in constant stack, as the ATS does.

The conversion is mechanical.  Every recursive call in the original is in
tail position, so each becomes "overwrite the parameters, loop again":

    return search (bd, i-1, board_get (bd, i-1) + 1, nsol)
    ==>
    bd, i, j, nsol = bd, i-1, board_get (bd, i-1) + 1, nsol
    continue

Python evaluates the whole right-hand side before assigning, so the old [i]
and [bd] are still in scope while the new arguments are computed -- exactly
the semantics of evaluating a call's arguments before entering it.

Everything else is untouched: the board is still an immutable 8-tuple,
[board_get] / [board_set] keep their if-chains, and the function names,
arguments and return values are unchanged.

Run: python3 eight_queens_loop.py
"""

N = 8

# typedef int8 = (int, int, int, int, int, int, int, int)
int8 = tuple  # an 8-tuple of ints


def print_dots(i: int) -> None:
    # was: if i > 0 then (print ". "; print_dots (i-1)) else ()
    while i > 0:
        print(". ", end="")
        i = i - 1
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
    print()
# end of [print_board]


def board_get(bd: int8, i: int) -> int:
    # not recursive in the original; unchanged
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
    # not recursive in the original; unchanged
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
    # not recursive in the original; unchanged
    return j0 != j1 and abs(i0 - i1) != abs(j0 - j1)
# end of [safety_test1]


def safety_test2(i0: int, j0: int, bd: int8, i: int) -> bool:
    # The recursive call [safety_test2 (i0, j0, bd, i-1)] only ever changes
    # [i], so the loop only has to decrement it.
    while i >= 0:
        if safety_test1(i0, j0, i, board_get(bd, i)):
            i = i - 1
        else:
            return False
    return True
# end of [safety_test2]


def search(bd: int8, i: int, j: int, nsol: int) -> int:
    while True:
        if j < N:
            test = safety_test2(i, j, bd, i - 1)
            if test:
                bd1 = board_set(bd, i, j)
                if i + 1 == N:
                    print("Solution #", nsol + 1, ":\n\n", sep="", end="")
                    print_board(bd1)
                    # search (bd, i, j+1, nsol+1) -- note [bd], not [bd1]:
                    # row i is about to be overwritten by the next column.
                    j, nsol = j + 1, nsol + 1
                    continue
                else:
                    # search (bd1, i+1, 0, nsol) -- positioning next piece
                    bd, i, j = bd1, i + 1, 0
                    continue
            else:
                # search (bd, i, j+1, nsol)
                j = j + 1
                continue
        else:
            if i > 0:
                # search (bd, i-1, board_get (bd, i-1) + 1, nsol)
                # RHS is evaluated first, so [i] here is still the old row.
                i, j = i - 1, board_get(bd, i - 1) + 1
                continue
            else:
                return nsol
# end of [search]


def main0() -> None:
    bd0: int8 = (0, 0, 0, 0, 0, 0, 0, 0)
    nsol = search(bd0, 0, 0, 0)  # (bd, i, j, nsol)
    print("The total number of solutions is ", nsol, ".\n", sep="", end="")
# end of [main0]


if __name__ == "__main__":
    # No sys.setrecursionlimit and no big-stack thread: that is the whole
    # point of this variant.  It runs in constant stack, as the ATS does.
    main0()
#
# end of [eight_queens_loop.py]
