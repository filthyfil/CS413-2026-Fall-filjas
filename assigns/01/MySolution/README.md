# Assignment 01 — Eight Queens: ATS → Python 3

AI-assisted translation of the eight-queens program from
[*Introduction to Programming in ATS*](https://ats-lang.github.io/FROZEN000/DOCUMENT/INT2PROGINATS/HTML/INT2PROGINATS-BOOK-onechunk.html#example-the-eight-queens-puzzle)
into Python 3, with an independent review and test suite.

Both programs print all 92 solutions to the 8×8 puzzle and the total. Their
output is **byte-for-byte identical** (14012 bytes, 1013 lines).

---

## AI Reflection

<!--
  Assignment task 8: ~200-400 words covering what the AI did well, what
  mistakes or weaknesses you found, what you had to understand yourself to
  verify the translation, whether the generated version could have been
  trusted without testing, and how AI affected your work.
-->

The README is AI generated and details the general implementation and usage. The AI did a great job at translating the source program into python quickly. However, there leaves a bit to be wanted: Making poor design decisions to align too closely to the specification. Creating and using a function just for the point of printing a new line is probably not the wisest thing, especially since `print()` counts as a function call, and should be considered "close enough to source". I read a little bit about tail-recursion in ATS, from the docs (`https://en.wikibooks.org/wiki/ATS:_Programming_with_Theorem-Proving/Tail-call_and_Tail-recursion`). I also installed the compiler to verify the source program, and for testing. Reading the doc on tail recursion leads me to think that implementing the a loop in python for the algorithm is closer to source, which led to the implementation of the looped variant `eight_queens_loop.py`. I think the generated version in this case can be trusted without testing, the translation seemed to be roughly one-to-one, minus the stack hack. AI made the development cycle way faster, but to audit the code well took a lot longer since the code was unfamiliar. AI also uses a lot of keywords that I am unfamiliar with, especially for the bash scripting, and test cases written in AST.

The AI, in its review, flagged four "defects" in the source code, which I deem to not really be defects. In the implementation, it is very clear what is happening, and nontermination on i>=9, is not a problem because this is not possible in the case of solving eight-queens. The backtrack defect, is not in scope of the solver; the N=8 is hardcoded because this is chess. Not a problem. 

Arguably, it could be parameterized, but there is no reason to in the problem of eight-queens on a chess board.

Overall, was OK.

---

## Quick start

```sh
./run_tests.sh          # build everything, run every check; exits 0 on success
```

Individually:

```sh
patscc -DATS_MEMALLOC_LIBC -o eight_queens eight_queens.dats
./eight_queens                      # the ATS original
python3 eight_queens.py             # the translation
python3 eight_queens_loop.py        # iterative variant of the translation
```

Requires ATS2/Postiats (tested on 0.4.2) and Python 3 (tested on 3.10).
Python needs no third-party packages.

---

## Files

### Programs

| File | Role |
|---|---|
| `source_code_snippets.txt` | The instructor's original ATS snippets, **never modified** |
| `eight_queens.dats` | The original, plus the prelude include and a `main0` |
| `eight_queens.py` | Hand translation — keeps the recursive shape of the ATS |
| `eight_queens_loop.py` | Same program with the tail calls written as loops |

### Tests

| File | Role |
|---|---|
| `run_tests.sh` | Six-layer runner (see below) |
| `test_queens.dats` | ATS test driver, 42 cases |
| `test_queens.py` | Python test driver, the same 42 cases |
| `output_ats.txt`, `output_py.txt` | Frozen whole-program goldens |
| `expected_tests.txt` | Frozen `## ` markers from a reviewed suite run |
| `TEST-RESULTS.md` | Findings, defects, full test inventory |

### Documentation

| File | Role |
|---|---|
| `AI-TRANSCRIPT.md` | Prompts, summarized AI responses, manual changes |
| `TEST-RESULTS.md` | Test results and the four defects found |

Build artifacts (`eight_queens`, `test_queens`, `*_dats.c`, `out/`,
`__pycache__/`) are gitignored.

---

## What the test suite checks

`run_tests.sh` runs six layers and exits nonzero if any fails:

| Layer | Checks |
|---|---|
| 0 | The instructor's eight functions are still byte-identical to `source_code_snippets.txt` |
| 1 | Both ATS programs build |
| 2 | Whole-program output: ATS vs frozen golden, and ATS vs Python |
| 3 | 42 per-function cases, ATS vs Python, full stdout byte-compared |
| 4 | A documented non-termination defect still reproduces (under timeout) |
| 5 | The iterative variant matches the ATS and runs in constant stack |

The 42 cases are written **twice** — once in ATS, once in Python, in the same
order with the same names and output format — so agreement between the two
implementations is verified by `diff`, not by eye.

`test_queens.py` takes the module under test from an environment variable, so
one suite covers both Python variants:

```sh
QUEENS_MODULE=eight_queens_loop python3 test_queens.py
```

---

## Notes on the translation

**What was preserved.** The board stays an immutable 8-tuple (index = row,
value = column). Every function keeps its ATS name, parameter list and return
value, including the `~1` sentinel from `board_get` and the silent no-op of an
out-of-range `board_set`. `board_get`/`board_set` keep their if-chains, which
exist because ATS cannot project a tuple at a runtime index.

**Tail calls.** ATS compiles a tail call into a jump, so `search`'s 17,685
successive calls cost no stack. Python has no tail-call elimination, so the two
Python files answer that differently:

| | `eight_queens.py` | `eight_queens_loop.py` |
|---|---|---|
| Recursive shape of the original | preserved | replaced by loops |
| Peak frame depth, full run | 17,685 | 5 |
| Needs recursion limit + big-stack thread | yes | no |

Both produce identical output and pass all 42 cases. They differ on exactly one
input — a defective one — described in `TEST-RESULTS.md`.

**Testing the ATS.** ATS functions in a `.dats` are invisible to another
compilation unit, and two `main` implementations cannot coexist. Rather than
restructure the file, six lines guard `main0`:

```ats
#ifdef
EIGHT_QUEENS_NO_MAIN
#then
#else
implement main0 () = ...
#endif
```

`test_queens.dats` defines that symbol and `#include`s the program. This is the
idiom ATS itself ships with (`$PATSHOME/contrib/ATS-extsolve-z3/`). Every
function keeps its original line number, and Layer 0 proves the algorithm was
never touched.

---

## Defects found in the original

Four, all latent under the program's fixed entry point. Full detail in
`TEST-RESULTS.md`.

1. **`search` does not terminate for `i >= 9`.** `board_set` silently drops an
   out-of-range write while the row counter keeps climbing. ATS loops forever;
   the recursive Python raises `RecursionError` instead — the one place the two
   implementations diverge.
2. **`search` never validates the board it is handed.** An inconsistent seed
   produces fabricated solutions (96 instead of 92).
3. **The backtrack branch has no floor**, so `search` cannot solve a partial
   board — a seeded call means "resume the scan here", not "complete this
   prefix".
4. **`N` is not a single source of truth.** Rebuilding with `#define N 4` gives
   the correct count but malformed boards, because `print_board`, `board_get`,
   `board_set` and `int8` are independently hardcoded to 8.

