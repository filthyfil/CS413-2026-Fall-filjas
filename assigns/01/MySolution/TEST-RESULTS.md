# Test Results — Eight Queens (ATS original vs Python translation)

**Date:** 2026-09-07
**Under test:** `eight_queens.dats` (ATS2/Postiats 0.4.2) and `eight_queens.py` (Python 3.10)
**Test files:** `test_queens.dats`, `test_queens.py`, driven by `run_tests.sh`

Reproduce everything below with:

```sh
./run_tests.sh          # exits 0 on success, 1 on any failure
```

---

## 1. Summary

| Layer | What it checks | Result |
|---|---|---|
| 0 | Instructor's eight functions still byte-identical to `source_code_snippets.txt` | **PASS** (116 lines) |
| 1 | Both programs build (`patscc -DATS_MEMALLOC_LIBC`) | **PASS** |
| 2 | Whole-program output vs frozen golden, and ATS vs Python | **PASS** (14012 bytes identical) |
| 3 | 42 per-function cases, ATS vs Python | **PASS** (42/42 both sides; 278726 bytes of stdout identical) |
| 4 | Documented non-termination still reproduces | **PASS** |
| 5 | Iterative variant matches ATS (output, 42 cases, constant stack) | **PASS** |

**42 tests, 0 failures, on both implementations.** The two drivers' stdout is
byte-for-byte identical, so agreement is verified mechanically rather than by eye.

Four genuine defects were found in the original algorithm (§3). All are latent
under `main0`'s fixed entry point and none affect the headline answer of 92 —
but three of them are reachable the moment `search` is called with anything
other than `(bd0, 0, 0, 0)`, and one (D1) behaves *differently* in the two
languages.

---

## 2. How the program had to be made testable

ATS functions defined in a `.dats` are invisible to another compilation unit,
and two `main` implementations cannot coexist in one program. Rather than split
the file into `.sats`/`.dats` — which would have destroyed byte-identity with
the instructor's snippets — six lines were added *below* all eight functions,
guarding only `main0`:

```ats
#ifdef
EIGHT_QUEENS_NO_MAIN
#then
#else
implement main0 () = ...   // unchanged
#endif
```

`test_queens.dats` then does `#define EIGHT_QUEENS_NO_MAIN 1` followed by
`#include "./eight_queens.dats"` and supplies its own `main1`. This is the
idiom ATS itself ships with (`$PATSHOME/contrib/ATS-extsolve-z3/DATS/SOLVING/`).
Every function keeps its original line number; Layer 0 proves the algorithm was
never touched, and Layer 2 proves the program's output did not change.

---

## 3. Defects and edge cases found

### D1 — `search` does not terminate for `i >= 9`  *(severity: high)*

`board_set` silently ignores an out-of-range row, so the write is dropped while
the row counter keeps climbing. With `i = 9`, `safety_test2` compares the
candidate against `board_get(bd, 8) = ~1`, which fails the diagonal test, so
every column is rejected; `j` reaches `N`, the backtrack branch resets
`j = board_get(bd, 8) + 1 = 0` and `i = 8` — and the state repeats forever.

**This is the one place the two implementations genuinely diverge:**

| | `search(bd0, 9, 0, 0)` |
|---|---|
| ATS | **Loops forever** — tail calls are jumps, so the stack never grows |
| Python | **`RecursionError: maximum recursion depth exceeded in comparison`** |

Same defect, different symptom, caused entirely by the tail-call-elimination
gap. The Python version fails *louder*, which is arguably safer, but a caller
catching `RecursionError` would see a bug the ATS version can never report.
Verified under a 10-second timeout (ATS exit 124); Layer 4 pins it.

### D2 — `search` never validates the board it is handed  *(severity: medium)*

`safety_test2` only checks a *new candidate* against rows below it. Nothing
ever checks the seeded rows against each other, so an inconsistent prefix
produces fabricated solutions that are printed as if genuine:

| Seed | Returns | Truth |
|---|---|---|
| `search((0,1,0,…), 2, 0, 0)` | 96 | 92 — four boards have queens at (0,0) and (1,1), a diagonal pair |
| `search((0,0,0,…), 2, 0, 0)` | 98 | 92 — six fabricated boards |

This is an undocumented precondition: *the caller must guarantee `bd[0..i-1]`
is already mutually consistent.* Pinned as a characterization test (T10) so
that a future fix shows up as a deliberate failure.

### D3 — `search`'s backtrack branch has no floor  *(severity: low / by design)*

`if i > 0 then search (bd, i-1, board_get (bd, i-1) + 1, nsol)` stops only at
row 0, so `search` always climbs above whatever row it was started on. The
consequence is that **`search` cannot solve a partial board.** Seeding a prefix
does not constrain the result; it selects a *resume point* in one fixed scan:

| Seed `bd[0]=c`, `i=1` | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| Result | 92 | 88 | 80 | 64 | 46 | 28 | 12 | 4 |

The successive differences are the per-first-column counts
**4, 8, 16, 18, 18, 16, 8, 4** — they sum to 92 and are mirror-symmetric
(`d[c] = d[7-c]`), which is a correctness oracle independent of the program.
Tests T9 assert the counts, the differences, and the symmetry.

Related: the `int8` type cannot represent an incomplete board at all. It is a
total 8-tuple with no "unoccupied" value, so `(0,0,0,0,0,0,0,0)` does not mean
*empty* — it means *eight queens in column 0*. It works only because `search`
never reads a row at or above `i`.

### D4 — `N` is not a single source of truth  *(severity: medium)*

`#define N 8` controls the search, but `int8`, `print_board`, `board_get` and
`board_set` are all independently hardcoded to 8. Rebuilding with `#define N 4`
gives the **correct count (2 solutions for 4-queens)** but malformed output —
`print_board` still emits eight rows, the last four being the unused tuple
slots:

```
Solution #1:

. Q . .
. . . Q
Q . . .
. . Q .
Q . . .     <- spurious
Q . . .     <- spurious
...
```

So the constant is not safely tunable, and no test can vary the board size
without editing four other places.

### Minor observations (correct, but worth recording)

- `safety_test1(3,3,3,3)` is `false` — a queen is not "safe" from itself,
  since `j0 != j1` fails. Harmless only because `search` always calls
  `safety_test2` with rows *strictly* below `i`.
- `safety_test1` never tests for a shared row; one queen per row is structural,
  not verified. `safety_test1(4,0,4,2)` returns `true`.
- `board_get` returns `~1` for an out-of-range *index*, never for "unoccupied" —
  the sentinel is easy to misread as the latter.
- `board_set` out of range is a silent no-op with no error signal (this is the
  proximate cause of D1).
- `search(bd, -1, 0, 0)` returns 92 by accident: `board_set` drops the write and
  `i+1 = 0 != N`, so it falls through to row 0.
- Python-only: calling `main0()` directly, without the big-stack thread in
  `__main__`, raises `RecursionError`. The ATS original runs in constant stack.

---

## 3a. The iterative variant (`eight_queens_loop.py`)

`eight_queens.py` keeps the recursive shape of the ATS original, which costs
17,685 live frames and needs `sys.setrecursionlimit` plus a 64 MB thread.
`eight_queens_loop.py` makes the opposite trade: `print_dots`, `safety_test2`
and `search` become loops. Every recursive call in the original is in tail
position, so each converts mechanically to "overwrite the parameters, loop
again". Python evaluates a whole right-hand side before assigning, which is
exactly the semantics of evaluating a call's arguments before entering it, so
`i, j = i - 1, board_get(bd, i - 1) + 1` reads the *old* `i` — as the ATS does.

Measured, not assumed:

| | `eight_queens.py` | `eight_queens_loop.py` |
|---|---|---|
| Peak frame depth, full run | 17,685 | **5** |
| Needs recursion limit + thread | yes | **no** |
| Whole-program output | identical to ATS | identical to ATS |
| The 42 per-function cases | 42/42 | **42/42, byte-identical** |
| **D1, `search(bd, 9, 0, 0)`** | `RecursionError` | **runs forever — matches ATS** |

That last row is the interesting one. The iterative variant is *less* faithful
structurally but *more* faithful semantically: on the D1 input it reproduces the
ATS behaviour exactly, where the recursive translation diverges by raising
`RecursionError`. Neither is wrong — they are different answers to the fact that
Python has no tail-call elimination — but it means the choice of encoding is
itself observable, and only on a defective input.

`test_queens.py` takes the module under test from `QUEENS_MODULE`, so the same
42 cases run against either implementation without duplicating the suite:

```sh
QUEENS_MODULE=eight_queens_loop python3 test_queens.py
```

---

---

## 4. Test inventory

42 cases in `test_queens.dats` / `test_queens.py`, in identical order with
identical names and output format.

| ID | Function | Category | Cases | Notable expectations |
|---|---|---|---|---|
| T1 | `board_get` | normal | 3 | indices 0, 3, 7 |
| T2 | `board_get` | **boundary** | 3 | `-1`, `8`, `99` → `~1` |
| T3 | `board_set` | normal | 3 | first/last/middle row; others undisturbed |
| T4 | `board_set` | **boundary** | 2 | `-1`, `8` → silent no-op (D1's cause) |
| T5 | `safety_test1` | normal + unusual | 6 | column, diagonal, anti-diagonal; self → `false`; same row → `true` |
| T6 | `safety_test2` | **boundary** | 4 | `i = -1` and `i = -5` → vacuous `true` |
| T7 | `search` | normal + boundary | 3 | full puzzle → 92; `j = 8` and `j = 99` at row 0 → 0 |
| T8 | `search` | **own design** | 2 | `nsol` seeded 5 → 97, 100 → 192 (pure accumulator) |
| T9 | `search` | **own design** | 13 | resume-point table, differences, mirror symmetry (D3) |
| T10 | `search` | **own design** | 2 | characterizes D2: illegal prefixes → 96, 98 |
| T11 | `search` | **boundary** | 1 | `i = 8` → 101, a nonsense count (D1) |
| — | `search` | **boundary** | (Layer 4) | `i = 9` → non-terminating; run under timeout, not in-suite |

Two mechanical safeguards worth noting:

- **Bools are never printed.** ATS emits `true`/`false`, Python emits
  `True`/`False`; both drivers funnel through `b2i` so the outputs stay
  diffable. Same reason `print_int8` is hand-written on both sides rather than
  using `str(tuple)` (which would insert spaces) or ATS `fprint_tup` (defined
  only for arities 2–4).
- **`assertloc` is not used.** It is `assert_errmsg`, which does
  `fprintf(stderr, …); exit(1)` on the first failure — it would abort the run
  and write to the wrong stream. A `(ntest, nfail)` accumulator is threaded
  through instead, mirroring `board_set`'s own shadowed-`val` style.
  `main1(): int` supplies the exit code, since `main0` returns `void` and would
  always exit 0.

---

## 5. One test failure worth reporting

The first run of T9 reported `## FAIL search/mirror: expected 0, got -4`.

**The program was right; the test was wrong.** The mirror pairing is
`d[c] = d[7-c]` where `d[c] = seed(c) - seed(c+1)` for `c < 7` and `d[7] = seed(7)`.
The assertion had paired `d[0]` against `d[6]` instead of `d[7]`. Corrected to
three assertions (`mirror0`, `mirror1`, `mirror3`), after which all 42 pass.

Recorded here because it is the one case where the suite caught a real error
during development, and because it illustrates the risk in this whole exercise:
an oracle derived from the program under test proves nothing. The per-column
counts are trustworthy precisely because they can be checked against the known
mathematics of the 8-queens problem, not against the program's own output.

---

## 6. Files

| File | Role |
|---|---|
| `source_code_snippets.txt` | Instructor's original, never modified |
| `eight_queens.dats` | Original + prelude include + `main0` (guarded) |
| `eight_queens.py` | Hand translation, recursive (mirrors the ATS shape) |
| `eight_queens_loop.py` | Same program with the tail calls written as loops |
| `test_queens.dats` | ATS test driver (42 cases) |
| `test_queens.py` | Python test driver (same 42 cases, same output) |
| `run_tests.sh` | Four-layer runner |
| `output_ats.txt`, `output_py.txt` | Frozen whole-program goldens |
| `expected_tests.txt` | Frozen `## ` markers from a reviewed run |

Goldens are frozen from a hand-reviewed run and committed; they are **not**
regenerated by `run_tests.sh`, since a golden the script rewrites can never fail.
