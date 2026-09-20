# Assign 02 - expanding the LAMBDA language

## Author: Filip Jasionek 

### What are the changes?

Added support for pairs and projections, as well as support for size, fvset, and subst0. Which all add more support for writing useful programs in the lambda language.

Unit tests were added to verify the correctness of the new additions.

The ATS program was rewritten, as much as possible, in the new lambda language. The mapping between data and operators is below.

| ATS2 | LAMBDA0 | Notes |
| --- | --- | --- |
| `int`, `bool` | `T0Mint`, `T0Mbtf` | |
| `int8 = (int, ..., int)` | right-nested pairs `T0Mpair(x0, T0Mpair(x1, ... T0Mpair(x6, x7)))` | `board_term` |
| `bd.k` | `T0Mpfst(T0Mpsnd^k(bd))`, or `T0Mpsnd^7(bd)` for the last slot | `field(bd, k, n)` |
| multi-argument function `f (a, b, c)` | one tuple argument `_arg`; `a = fst _arg`, `b = fst (snd _arg)`, ... | the `T0Mfix` functions |
| `a andalso b` | `T0Mif0(a, b, T0Mbtf(False))` | short-circuit preserved |
| `abs` (prelude) | `ABS = λx. if x < 0 then -x else x` | uses `T0Mop1("-")` |
| `print!` / `print_board` | accumulator `sols`; each solved board folded in as `sols * n^n + board_pack(bd1)` | `board_pack_term` |
| `board_get (bd, i)` | `board_get_term(n)` | `λbd i.` chain of `n` `T0Mif0(i == k, bd.k, ...)`, else `-1` |
| `board_set (bd, i, j)` | `board_set_term(n)` | `λbd i j.` chain of `n` `T0Mif0`s, each rebuilding the tuple with slot `k` replaced by `j`; else `bd` |
| `safety_test1 (i0, j0, i1, j1)` | `SAFETY_TEST1` | curried `λi0 j0 i1 j1. if j0 != j1 then abs(i0-i1) != abs(j0-j1) else false` |
| `safety_test2 (i0, j0, bd, i)` | `safety_test2_term(n)` | `T0Mfix("safety_test2", "_arg", ...)`, recursing on `(i0, j0, bd, i-1)` |
| `search (bd, i, j, nsol)` | `search_term(n)` | `T0Mfix("search", "_arg", ...)`, line for line, with a fifth tuple slot `sols` |
| `search` (restructured) | `search_tree_term(n)` | same search as tree recursion; used for 8x8 |
| `main0` | `queens_term(n)` / `queens_tree_term(n)` | `search` applied to `((0,...,0), 0, 0, 0, 0)`; value is the pair `(nsol, sols)` |

The only changes from the source program's meaning are the representation of data for the board, the need for an accumulator for the solution count, since CBV term can't. So its packed. Python code unpacks it and prints the solutions.

Finally, a limitation is one we saw in the previous assignment where the stack gets very large. The current tail-recursive implementation did not run on my machine, (OOM) so I needed to revise the search by using tree recursion. One may use the tree recursive approach by specifying the `--tree` flag on the command. This is also detailed below.

### How do I run the tests?

Python >= 3.12 is required (`type X = ...` aliases in the starter).

```sh
cd assigns/02/MySolution
PY="uv run --python 3.12 --no-project python"   # or PY=python3.12
```

| What | Command |
| --- | --- |
| Original ATS2 program | `patscc -DATS_MEMALLOC_LIBC -o eight_queens eight_queens.dats && ./eight_queens` |
| Translation, 8x8, tree-recursive search (~6 min) | `$PY queens_lambda0.py 8 --tree` |
| Translation, 8x8, line-for-line search (several GB) | `$PY queens_lambda0.py 8` |
| Translation on a smaller board | `$PY queens_lambda0.py 6` |
| Diff the translation against the ATS output | `$PY queens_lambda0.py 8 --tree \| diff - output_ats.txt` |
| Interpreter tests (starter + pairs/projections) | `cd TEST && $PY -m unittest test01_lambda0 test02_lambda0 -v` |
| Queens tests, fast subset (~25 s) | `cd TEST && QUEENS_SKIP_FULL=1 $PY -m unittest test03_queens -v` |
| Queens tests including the 8x8 run (~6 min) | `cd TEST && $PY -m unittest test03_queens -v` |
| Everything via the Makefile | `cd TEST && make PYTHON="$PY"` |

### Summary

Overall, the runtime performance of the python interpreter is not good. Obviously, clever mechanisms are needed to support the functional language that heavily use tail-recursion. 

### Human in the loop? What did I do

I reviewed the lambda implementation, and verified the logical functionality. I majorly tested the results by comparing the output of the ATS program and the lambda program. 
