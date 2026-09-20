"""The eight-queens puzzle as a LAMBDA0 term.

This is a translation of eight_queens.dats (copied next to this file from
assigns/01/MySolution) into a closed term of type t0erm, written with the AST
constructors of lambda0.py and evaluated by its t0erm_cbv_evaluate0.  The
search and the queen-conflict checks are inside the term; Python only builds
the AST, hands it to the interpreter, and decodes/prints the resulting value.

Run with: python3 queens_lambda0.py [N] [--tree]      (N defaults to 8)
Requires Python 3.12 or later, like lambda0.py.

The default `search` is the ATS search line for line.  On an 8x8 board it
needs several GB of memory in this interpreter (see search_term); `--tree`
selects search_tree_term, which finds the same solutions in the same order
in about 20 MB.

Representations
---------------
ATS2                          LAMBDA0
----------------------------  -------------------------------------------------
int, bool                     T0Mint, T0Mbtf
int8 = (int, ..., int)        an N-tuple: right-nested pairs
                              T0Mpair(x0, T0Mpair(x1, ... T0Mpair(x6, x7)))
bd.3                          T0Mpfst(T0Mpsnd(T0Mpsnd(T0Mpsnd(bd))))
fun f (a, b, c) = e           T0Mfix("f", "_arg", e): a recursive function
                              takes one tuple; a is T0Mpfst(T0Mvar("_arg")),
                              b is T0Mpfst(T0Mpsnd(T0Mvar("_arg"))), ...
fun g (bd, i) = e             T0Mlam("bd", T0Mlam("i", e)): the board helpers
                              are curried (see board_get_term)
a andalso b                   T0Mif0(a, b, T0Mbtf(False))
abs                           a T0Mlam term (no abs primitive is added)
print! / print_board          not expressible: `search` carries an accumulator
                              acc = (nsol, sols); sols is an integer into which
                              each solved board is packed (base N, see
                              board_pack_term).  The program's value is the
                              pair (nsol, sols); Python decodes and prints it
                              in the ATS format.
search (tail-recursive loop)  search_term, line for line.  search_tree_term
                              is the same search as tree recursion (see its
                              docstring for why it exists).

Where a term is used inside another (abs inside safety_test1, board_get inside
safety_test2, ...), the Python name simply stands for that term, so the term
is embedded at that point: LAMBDA0 has no definitions.  Every term here is
closed.  Python loops are used only to write out the N-way if-chains of the
board helpers, as test01 does for Church numerals.
"""

import sys
import threading
from pathlib import Path

# Import the extended interpreter from this directory, not the starter file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda0 import (
    T0Mint, T0Mbtf, T0Mvar, T0Mlam, T0Mfix, T0Mapp, T0Mif0, T0Mop1, T0Mop2,
    T0Mpair, T0Mpfst, T0Mpsnd,
    t0erm_fvset, t0erm_size, t0erm_cbv_evaluate0,
)

N = 8

########################################################################
# abs (x) = if x < 0 then ~x else x           (a prelude function in ATS)
########################################################################

x = T0Mvar("x")

ABS = T0Mlam("x",
    T0Mif0(T0Mop2("<", x, T0Mint(0)),
        T0Mop1("-", x),
        x))

########################################################################
# Boards: the ATS int8 tuple becomes an N-tuple of right-nested pairs.
########################################################################

def board_term(columns):
    """(c0, c1, ..., c7) as T0Mpair(T0Mint(c0), T0Mpair(T0Mint(c1), ...))."""
    *init, last = [T0Mint(c) for c in columns]
    for t in reversed(init):
        last = T0Mpair(t, last)
    return last


def field(bd, k, n):
    """bd.k for an n-tuple: fst (snd (... (snd bd))), or just snd^k bd for the last."""
    for _ in range(k):
        bd = T0Mpsnd(bd)
    return bd if k == n - 1 else T0Mpfst(bd)


def board_get_term(n=N):
    """fun board_get (bd, i) =
         if i = 0 then bd.0 else if i = 1 then bd.1 ... else ~1

    Curried: `i` is compared up to n times, and a substituted integer is
    free to look at, while a component of a tuple parameter would re-evaluate
    the whole tuple each time.
    """
    bd, i = T0Mvar("bd"), T0Mvar("i")
    body = T0Mint(-1)
    for k in reversed(range(n)):
        body = T0Mif0(T0Mop2("==", i, T0Mint(k)),
                      field(bd, k, n),
                      body)
    return T0Mlam("bd", T0Mlam("i", body))


def board_set_term(n=N):
    """fun board_set (bd, i, j) =
         if i = 0 then (j, x1, ..., x7) else if i = 1 then (x0, j, x2, ...) ... else bd
    """
    bd, i, j = T0Mvar("bd"), T0Mvar("i"), T0Mvar("j")
    body = bd
    for k in reversed(range(n)):
        *init, last = [j if m == k else field(bd, m, n) for m in range(n)]
        for t in reversed(init):
            last = T0Mpair(t, last)
        body = T0Mif0(T0Mop2("==", i, T0Mint(k)),
                      last,
                      body)
    return T0Mlam("bd", T0Mlam("i", T0Mlam("j", body)))


def board_pack_term(n=N):
    """Pack a board into one integer: x0 + n*(x1 + n*(x2 + ...)).

    Stands in for print_board: the ATS program prints each solution as a side
    effect, which a pure term cannot do, so solutions are accumulated instead.
    """
    bd = T0Mvar("bd")
    body = T0Mint(0)
    for k in reversed(range(n)):
        body = T0Mop2("+", field(bd, k, n), T0Mop2("*", T0Mint(n), body))
    return T0Mlam("bd", body)

########################################################################
# fun safety_test1 (i0, j0, i1, j1) =
#   j0 != j1 andalso abs (i0 - i1) != abs (j0 - j1)
########################################################################

i0, j0, i1, j1 = T0Mvar("i0"), T0Mvar("j0"), T0Mvar("i1"), T0Mvar("j1")

SAFETY_TEST1 = T0Mlam("i0", T0Mlam("j0", T0Mlam("i1", T0Mlam("j1",
    T0Mif0(T0Mop2("!=", j0, j1),
        T0Mop2("!=",
            T0Mapp(ABS, T0Mop2("-", i0, i1)),
            T0Mapp(ABS, T0Mop2("-", j0, j1))),
        T0Mbtf(False))))))

########################################################################
# fun safety_test2 (i0, j0, bd, i) =
#   if i >= 0 then
#     if safety_test1 (i0, j0, i, board_get (bd, i))
#       then safety_test2 (i0, j0, bd, i-1) else false
#   else true
########################################################################

def safety_test2_term(n=N):
    board_get = board_get_term(n)
    arg = T0Mvar("_arg")                          # the tuple (i0, j0, bd, i)
    i0 = T0Mpfst(arg)
    j0 = T0Mpfst(T0Mpsnd(arg))
    bd = T0Mpfst(T0Mpsnd(T0Mpsnd(arg)))
    i = T0Mpsnd(T0Mpsnd(T0Mpsnd(arg)))
    safety_test2 = T0Mvar("safety_test2")
    return T0Mfix("safety_test2", "_arg",
        T0Mif0(T0Mop2(">=", i, T0Mint(0)),
            T0Mif0(T0Mapp(T0Mapp(T0Mapp(T0Mapp(SAFETY_TEST1, i0), j0), i),
                          T0Mapp(T0Mapp(board_get, bd), i)),
                T0Mapp(safety_test2,
                       T0Mpair(i0, T0Mpair(j0, T0Mpair(bd, T0Mop2("-", i, T0Mint(1)))))),
                T0Mbtf(False)),
            T0Mbtf(True)))

########################################################################
# fun search (bd, i, j, nsol) : int
########################################################################

def search_term(n=N):
    """The ATS search, line for line, with parameter tuple (bd, i, j, nsol, sols).

    Differences from the ATS:
    * N is baked in as T0Mint(n) so smaller boards can be tried.
    * print!/print_board are replaced by a fifth parameter sols: a solved
      board bd1 is appended as sols * n^n + board_pack(bd1), and the result
      is the pair (nsol, sols) instead of just nsol.
    * The single-use `val test` and `val bd1` bindings are inlined.

    Memory.  Every call here is a tail call, and ATS runs the whole search in
    constant stack.  The substitution interpreter has no tail-call
    elimination: each of the ~18 000 calls of an 8x8 search nests further
    Python calls and keeps its own freshly substituted copy of this
    ~1300-node body alive until the search ends -- several GB in total (a
    6x6 board, ~1 400 calls, is fine).  search_tree_term below restructures
    the recursion so that this does not happen and is used for the 8x8
    tests; the two agree on every board size tried.
    """
    board_get, board_set, board_pack = board_get_term(n), board_set_term(n), board_pack_term(n)
    safety_test2 = safety_test2_term(n)
    arg = T0Mvar("_arg")                          # the tuple (bd, i, j, nsol, sols)
    bd = T0Mpfst(arg)
    i = T0Mpfst(T0Mpsnd(arg))
    j = T0Mpfst(T0Mpsnd(T0Mpsnd(arg)))
    nsol = T0Mpfst(T0Mpsnd(T0Mpsnd(T0Mpsnd(arg))))
    sols = T0Mpsnd(T0Mpsnd(T0Mpsnd(T0Mpsnd(arg))))
    search = T0Mvar("search")
    bd1 = T0Mapp(T0Mapp(T0Mapp(board_set, bd), i), j)              # val bd1 = board_set (bd, i, j)
    test = T0Mapp(safety_test2,                                     # val test = safety_test2 (i, j, bd, i-1)
                  T0Mpair(i, T0Mpair(j, T0Mpair(bd, T0Mop2("-", i, T0Mint(1))))))

    def call_search(bd, i, j, nsol, sols):
        return T0Mapp(search, T0Mpair(bd, T0Mpair(i, T0Mpair(j, T0Mpair(nsol, sols)))))

    return T0Mfix("search", "_arg",
        T0Mif0(T0Mop2("<", j, T0Mint(n)),
            T0Mif0(test,
                T0Mif0(T0Mop2("==", T0Mop2("+", i, T0Mint(1)), T0Mint(n)),
                    # print_board bd1; search (bd, i, j+1, nsol+1)
                    call_search(bd, i, T0Mop2("+", j, T0Mint(1)),
                                T0Mop2("+", nsol, T0Mint(1)),
                                T0Mop2("+", T0Mop2("*", sols, T0Mint(n ** n)),
                                            T0Mapp(board_pack, bd1))),
                    # search (bd1, i+1, 0, nsol)      -- positioning next piece
                    call_search(bd1, T0Mop2("+", i, T0Mint(1)), T0Mint(0), nsol, sols)),
                # search (bd, i, j+1, nsol)
                call_search(bd, i, T0Mop2("+", j, T0Mint(1)), nsol, sols)),
            T0Mif0(T0Mop2(">", i, T0Mint(0)),
                # search (bd, i-1, board_get (bd, i-1) + 1, nsol)   -- backtrack
                call_search(bd, T0Mop2("-", i, T0Mint(1)),
                            T0Mop2("+", T0Mapp(T0Mapp(board_get, bd), T0Mop2("-", i, T0Mint(1))),
                                        T0Mint(1)),
                            nsol, sols),
                T0Mpair(nsol, sols))))


def search_tree_term(n=N):
    """The ATS search as tree recursion, with parameter tuple (bd, i, j, acc).

    acc is the pair (nsol, sols).  Row i is scanned from column j upward,
    exactly as in the ATS: an unsafe column moves on to j+1; a safe one on the
    last row records the board; a safe one elsewhere places the queen and
    searches the next row from column 0.  The one change is what happens when
    that inner search finishes or when a row is exhausted.  The ATS *backtracks
    by hand*: `search (bd, i-1, board_get (bd, i-1) + 1, nsol)` reopens the
    previous row just past its queen.  Here the inner search simply *returns*
    its accumulator to the pending `search (bd, i, j+1, ...)`, which still
    holds the old board, so backtracking is the ordinary return of a recursive
    call.  Placements are visited in the same order, so the solutions come out
    in the same order as the ATS output.

    The recursion is now at most about n*n deep instead of one chain of every
    step of the search, which is what makes the 8x8 board feasible in a
    substitution interpreter (see search_term).
    """
    board_set, board_pack = board_set_term(n), board_pack_term(n)
    safety_test2 = safety_test2_term(n)
    arg = T0Mvar("_arg")                          # the tuple (bd, i, j, acc)
    bd = T0Mpfst(arg)
    i = T0Mpfst(T0Mpsnd(arg))
    j = T0Mpfst(T0Mpsnd(T0Mpsnd(arg)))
    acc = T0Mpsnd(T0Mpsnd(T0Mpsnd(arg)))
    nsol, sols = T0Mpfst(acc), T0Mpsnd(acc)
    search = T0Mvar("search")
    bd1 = T0Mapp(T0Mapp(T0Mapp(board_set, bd), i), j)
    test = T0Mapp(safety_test2,
                  T0Mpair(i, T0Mpair(j, T0Mpair(bd, T0Mop2("-", i, T0Mint(1))))))
    # print_board bd1  ==>  (nsol + 1, sols * n^n + board_pack bd1)
    record = T0Mpair(T0Mop2("+", nsol, T0Mint(1)),
                     T0Mop2("+", T0Mop2("*", sols, T0Mint(n ** n)), T0Mapp(board_pack, bd1)))

    def call_search(bd, i, j, acc):
        return T0Mapp(search, T0Mpair(bd, T0Mpair(i, T0Mpair(j, acc))))

    return T0Mfix("search", "_arg",
        T0Mif0(T0Mop2("<", j, T0Mint(n)),
            T0Mif0(test,
                # Safe: finish with this placement (record it, or search the
                # next row), then continue this row at j+1 with the result.
                call_search(bd, i, T0Mop2("+", j, T0Mint(1)),
                            T0Mif0(T0Mop2("==", T0Mop2("+", i, T0Mint(1)), T0Mint(n)),
                                   record,
                                   call_search(bd1, T0Mop2("+", i, T0Mint(1)), T0Mint(0), acc))),
                call_search(bd, i, T0Mop2("+", j, T0Mint(1)), acc)),
            # Row exhausted: hand the accumulator back to the caller.
            acc))

########################################################################
# implement main0 () = let val bd0 = (0, ..., 0) in search (bd0, 0, 0, 0) end
########################################################################

def queens_term(n=N):
    """The whole program.  Evaluates to the pair (nsol, sols)."""
    return T0Mapp(search_term(n),
        T0Mpair(board_term([0] * n),
        T0Mpair(T0Mint(0),
        T0Mpair(T0Mint(0),
        T0Mpair(T0Mint(0),
                T0Mint(0))))))


def queens_tree_term(n=N):
    """The same program built on search_tree_term; its acc is the pair (0, 0)."""
    return T0Mapp(search_tree_term(n),
        T0Mpair(board_term([0] * n),
        T0Mpair(T0Mint(0),
        T0Mpair(T0Mint(0),
                T0Mpair(T0Mint(0), T0Mint(0))))))

########################################################################
# Driver: evaluate the term and decode the result.
########################################################################

RECURSION_LIMIT = 10_000_000
THREAD_STACK = 1024 * 1024 * 1024


def evaluate(term):
    """Evaluate a term with room for the interpreter's nested Python calls.

    Each reduction step nests a Python call.  The tail-recursive search is
    one chain of every step (about 18 000 calls, each some tens of Python
    frames, for 8x8), so the default limit of 1000 is far too small.  The
    evaluation runs in a thread with a large stack; the limit is generous
    since Python 3.12 keeps pure-Python frames off the C stack.
    """
    result, error = [], []

    def run():
        sys.setrecursionlimit(max(sys.getrecursionlimit(), RECURSION_LIMIT))
        try:
            result.append(t0erm_cbv_evaluate0(term))
        except BaseException as e:      # re-raised in the calling thread
            error.append(e)

    threading.stack_size(THREAD_STACK)
    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]


def board_from_term(t, n=N):
    """Decode an n-tuple term of T0Mint into a Python tuple of ints."""
    columns = []
    for _ in range(n - 1):
        columns.append(t.arg1.arg1)
        t = t.arg2
    columns.append(t.arg1)
    return tuple(columns)


def boards_from_packed(sols, nsol, n=N):
    """Undo search's accumulation: nsol boards, most recent in the low digits."""
    boards = []
    for _ in range(nsol):
        sols, packed = divmod(sols, n ** n)
        board = []
        for _ in range(n):
            packed, column = divmod(packed, n)
            board.append(column)
        boards.append(tuple(board))
    assert sols == 0
    boards.reverse()
    return boards


def solve(n=N, program=queens_term):
    """Run the translated program; return (nsol, [boards in the order found])."""
    term = program(n)
    assert t0erm_fvset(term) == frozenset(), "queens term must be closed"
    value = evaluate(term)
    nsol = value.arg1.arg1
    return nsol, boards_from_packed(value.arg2.arg1, nsol, n)


def format_board(board, n=N):
    """print_board: one line per row, 'Q' in the queen's column."""
    return "".join(". " * c + "Q " + ". " * (n - c - 1) + "\n" for c in board)


def format_output(nsol, boards, n=N):
    """Reproduce the ATS program's output byte for byte."""
    out = [f"Solution #{k}:\n\n{format_board(board, n)}\n"
           for k, board in enumerate(boards, start=1)]
    out.append(f"The total number of solutions is {nsol}.\n")
    return "".join(out)


def main(argv):
    args = [a for a in argv[1:] if a != "--tree"]
    program = queens_tree_term if "--tree" in argv else queens_term
    n = int(args[0]) if args else N
    nsol, boards = solve(n, program)
    sys.stdout.write(format_output(nsol, boards, n))


if __name__ == "__main__":
    main(sys.argv)
