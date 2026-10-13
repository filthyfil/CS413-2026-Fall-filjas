# Assignment 5: Pretty Printing and Capture-Avoiding Substitution

I added two operations to the supplied LAMBDA AST, pretty printing and
capture-avoiding substitution. Both are visitors over `D0ExpVisitor` from
[`../lambda1_vp.py`](../lambda1_vp.py). I import the supplied files and don't
modify them.

| File | Contents |
| --- | --- |
| `lambda1_visitors.py` | `PrettyPrintVisitor`, `d0exp_pretty`; `AllNamesVisitor`, `FreshNames`, `SubstitutionVisitor`, `d0exp_substitute`; `DeBruijnVisitor`, `d0exp_alpha_equiv` (test aid) |
| `shared_cases.py` | Example inputs and expected results that both suites use |
| `test_unittest_suite.py` | `unittest.TestCase` suite |
| `test_pytest_suite.py` | pytest suite (plain functions and `assert`) |

## Requirements

| Needed for | Software | Tested with |
| --- | --- | --- |
| Code and unittest suite | Python 3.12 or later, standard library only | Python 3.12.14 |
| pytest suite | pytest (installed below) | pytest 9.1.1 |

Python 3.12 is required.

## Setup

From the assignment directory (`assigns/05`):

```sh
python3.12 -m venv .venv            # any Python >= 3.12
.venv/bin/pip install pytest
```

I used uv myself: `uv venv --python python3.12 .venv` and then
`uv pip install --python .venv/bin/python pytest`.
On Windows, use `.venv\Scripts\python` instead of `.venv/bin/python`.

## Running the tests

From the assignment directory, one command per suite:

```sh
.venv/bin/python -m unittest -v MySolution/test_unittest_suite.py   # unittest suite
.venv/bin/python -m pytest -v MySolution/test_pytest_suite.py       # pytest suite
```

The unittest suite only needs the standard library, so
`python3.12 -m unittest -v MySolution/test_unittest_suite.py` works without the
venv too. Running the tests leaves a `__pycache__/` next to `lambda1_vp.py`,
which isn't part of the submission.

## Examples

There's no parser or CLI (the assignment doesn't require one), so expressions
are written with the constructors:

```python
import sys; sys.path.insert(0, "MySolution")
from lambda1_visitors import d0exp_pretty, d0exp_substitute
from lambda1_vp import *

e = D0Eapp(D0Elam("x", D0Eop2("+", D0Evar("x"), D0Eint(1))), D0Eint(4))
d0exp_pretty(e)                    # '((lam x. (x + 1)) 4)'
d0exp_pretty(D0Eop2("/", D0Eint(1), D0Eint(0)))   # '(1 / 0)', not evaluated

e = D0Elam("y", D0Eop2("+", D0Evar("x"), D0Evar("y")))
d0exp_pretty(d0exp_substitute(e, "x", D0Evar("y")))   # '(lam y_1. (y + y_1))'
```

For trying things interactively, `.venv/bin/python -i MySolution/shared_cases.py`
gives you short constructor names like `V`, `I`, `lam`, `fix` and `add`.

Some more substitution results, in pretty-printed notation:

| Expression | Substitution | Result |
| --- | --- | --- |
| `(lam x. (x + y))` | `x := 3` | `(lam x. (x + y))` (shadowed) |
| `(let y = x in (x + y))` | `x := y` | `(let y_1 = y in (y + y_1))` |
| `(fix f(n). (x + (f n)))` | `x := (f + n)` | `(fix f_1(n_1). ((f + n) + (f_1 n_1)))` |
| `(fix f(f). (x + f))` | `x := f` | `(fix f_2(f_1). (f + f_1))` |
| `(lam y. ((x + y) + (lam y. y)))` | `x := y` | `(lam y_1. ((y + y_1) + (lam y. y)))` |
| `(pair (lam y. (x + y)) (lam y. (x + y)))` | `x := y` | `(pair (lam y_1. (y + y_1)) (lam y_2. (y + y_2)))` |

## Fresh-name policy

Every call to `d0exp_substitute(e, x, r)` makes one `FreshNames` supply. The
supply has a set of used names that starts out as every name in `e` and `r`,
free **and** bound (collected by `AllNamesVisitor`), plus the target `x`. To
rename a binder `b`, I take the first of `b_1`, `b_2`, `b_3`, ... that isn't in
the set, and add it to the set right away. All visitors in the call share the
same supply, including the ones doing the renaming, so a name never gets
generated twice. Names only depend on the inputs, so repeated calls give the
same output.

I only rename when I have to: the binder's name is free in `r` **and** the
target is free in the binder's scope. Otherwise bound names are left alone.
This is lazy renaming, not the Barendregt convention (making every binder
unique up front), since the assignment asks to avoid unnecessary renaming.

## Known limitations

- Free variables get recomputed at each binder, so substitution is quadratic in
  how deeply binders are nested. That's fine for test-sized expressions.
- All visitors recurse through `accept`, so expressions nested deeper than
  Python's recursion limit (about 1000 levels) raise `RecursionError`.
- Renaming a binder that already has a suffix adds another one: `y_1` becomes
  `y_1_1`. Still a valid identifier, just long.
- The result shares the replacement `r` (and unchanged subtrees of `e`) instead
  of copying them, which the assignment allows. If you mutated the result in
  place you'd also mutate those inputs; the visitors themselves never mutate.
- No input validation: variable and operator names aren't checked, and
  `D0E000()` raises `TypeError` like in the supplied visitors.
- `d0exp_alpha_equiv` is only a test aid. It compares De Bruijn forms, so free
  variables have to match by name.

## Design

Operations are written as visitors over the supplied excerpt and didn't touch the expression classes. Each node already has an accept that calls the matching `visit_*`, so the node's type picks the method (double dispatch design pattern).

**Result types.** D0ExpVisitor is generic in `R`, the type every `visit_*` returns, and each visitor picks its own. `PrettyPrintVisitor` is `D0ExpVisitor[str]`: each method formats its node and combines the strings its children return. `SubstitutionVisitor` is `D0ExpVisitor[d0exp]`, so it returns a new AST built from substituted children. The helpers use other types too: `AllNamesVisitor` returns a python frozenset of names, and `DeBruijnVisitor` returns a nameless tuple.

**Carrying context.** A visit method only gets the node. The interface fixes the signature, so instead of adding parameters, the visitor stores what it needs. These are set once in `__init__` and the visitor's own fields are only read after that. The one exception is the `FreshNames` supply: every visitor in a call shares it, and it changes on each rename, since each generated name is added to its used set. That shared, mutable set is what keeps names generated by different visitors from colliding. @dataclass decorator was not used because it does not read well, and __init__ is all that is needed. most methods just pass self down to the
children.

**Renaming and scope.** At a binder, stop if the binder is the target or if the target isn't free in the body. Otherwise, if the binder's name is free in the replacement, it would capture it, so I rename first. The rename is itself a substitution, that reads like `body[y := z]`, run by a new visitor sharing the same `FreshNames`. Since `z`is fresh, the rename never has to rename anything itself. For `let`, I substitute in the initializer, since it's outside the binder's scope. `fix` checks both binders. When the function name equals the parameter, I rename both, because renaming only the parameter would unshadow the function name and it would capture.

**Operations vs constructors.** Adding an operation is one new class, and the AST and the existing visitors stay the same. It is easy. Adding a constructor is more cumbersome; a new node class with accept, a new abstract `visit` in `D0ExpVisitor`, and a new method in every visitor. So Visitor fits when node types are stable and operations keep growing, which is the case for an interpreter. Hence a good fit for interpreter.
