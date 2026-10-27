"""Church-encoding library: closed target-AST combinators.

Every name here (TRUE, PAIR, Z, ...) is a Python name for a pure target term
built from Var, Lam, and App only; none is a target-language primitive. Each
combinator is closed, so applying it never captures names in its arguments.

    TRUE   = lam t. lam f. t
    FALSE  = lam t. lam f. f
    NUM(n) = lam s. lam z. s (s ... (s z))       -- s applied n times
    PAIR   = lam a. lam b. lam p. p a b
    Z      = lam g. (lam x. g (lam v. x x v)) (lam x. g (lam v. x x v))

Predecessor uses the pair ("sliding window") construction:

    SHIFT = lam p. PAIR (SND p) (SUCC (SND p))
    PRED  = lam n. FST (n SHIFT (PAIR NUM(0) NUM(0)))

Starting from (0, 0), each SHIFT maps (a, b) to (b, b + 1), so after n
shifts the pair is (n - 1, n) for n >= 1, and its first component is the
predecessor. For n = 0 no shift happens and FST yields 0, so PRED 0 = 0.

The boolean combinators AND and OR are strict: both arguments are values
before they are applied. The compiler implements the source's short-circuit
and/or with thunks instead, using TRUE/FALSE and I directly.

Python arithmetic is used only by num() to build a literal numeral.
Encoding references: A. Church, "The Calculi of Lambda-Conversion" (1941);
B. C. Pierce, "Types and Programming Languages" (2002), section 5.2
(Church booleans, numerals, pairs, and the pair-based predecessor) and
section 5.2's call-by-value fixed-point combinator.
"""
from __future__ import annotations

from target import Var, Lam, App, Term


def lam(*parts: str | Term) -> Term:
    """lam("x", "y", body) == Lam("x", Lam("y", body))."""
    body = parts[-1]
    if isinstance(body, str):
        raise TypeError("lam needs a body term after its parameter names")
    for p in reversed(parts[:-1]):
        if not isinstance(p, str):
            raise TypeError(f"lam parameters must be names, got {p!r}")
        body = Lam(p, body)
    return body


def app(fn: Term, *args: Term) -> Term:
    """app(f, a, b) == App(App(f, a), b): application associates left."""
    for a in args:
        fn = App(fn, a)
    return fn


def v(name: str) -> Var:
    return Var(name)


# Identity, used as the dummy value that forces a thunk.
I = lam("w", v("w"))

# Booleans ------------------------------------------------------------------
TRUE = lam("t", "f", v("t"))
FALSE = lam("t", "f", v("f"))
NOT = lam("b", app(v("b"), FALSE, TRUE))
AND = lam("p", "q", app(v("p"), v("q"), FALSE))
OR = lam("p", "q", app(v("p"), TRUE, v("q")))

# Pairs ---------------------------------------------------------------------
PAIR = lam("a", "b", "p", app(v("p"), v("a"), v("b")))
FST = lam("p", app(v("p"), TRUE))
SND = lam("p", app(v("p"), FALSE))


# Natural numbers -----------------------------------------------------------
def num(n: int) -> Term:
    """The Church numeral for n >= 0: lam s. lam z. s applied n times to z."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError(f"Church numerals encode naturals, got {n!r}")
    body: Term = v("z")
    for _ in range(n):
        body = App(v("s"), body)
    return lam("s", "z", body)


ZERO = num(0)
SUCC = lam("n", "s", "z", app(v("s"), app(v("n"), v("s"), v("z"))))
ISZERO = lam("n", app(v("n"), lam("x", FALSE), TRUE))

SHIFT = lam("p", app(PAIR, app(SND, v("p")), app(SUCC, app(SND, v("p")))))
PRED = lam("n", app(FST, app(v("n"), SHIFT, app(PAIR, ZERO, ZERO))))

ADD = lam("m", "n", "s", "z", app(v("m"), v("s"), app(v("n"), v("s"), v("z"))))
SUB = lam("m", "n", app(v("n"), PRED, v("m")))          # n-fold PRED of m
MUL = lam("m", "n", "s", app(v("m"), app(v("n"), v("s"))))

# Comparisons ---------------------------------------------------------------
# m <= n  iff  m - n = 0, using truncated subtraction.
LEQ = lam("m", "n", app(ISZERO, app(SUB, v("m"), v("n"))))
GEQ = lam("m", "n", app(LEQ, v("n"), v("m")))
LT = lam("m", "n", app(NOT, app(LEQ, v("n"), v("m"))))
GT = lam("m", "n", app(NOT, app(LEQ, v("m"), v("n"))))
EQ = lam("m", "n", app(AND, app(LEQ, v("m"), v("n")), app(LEQ, v("n"), v("m"))))
NEQ = lam("m", "n", app(NOT, app(EQ, v("m"), v("n"))))

# Recursion -----------------------------------------------------------------
# Call-by-value fixed point: the eta-expansion lam v. x x v delays the
# self-application until the recursive function is actually called.
_Z_HALF = lam("x", app(v("g"), lam("v", app(v("x"), v("x"), v("v")))))
Z = lam("g", app(_Z_HALF, _Z_HALF))

# Every closed combinator in the library, for purity and closedness checks.
COMBINATORS: dict[str, Term] = {
    "I": I, "TRUE": TRUE, "FALSE": FALSE, "NOT": NOT, "AND": AND, "OR": OR,
    "PAIR": PAIR, "FST": FST, "SND": SND,
    "ZERO": ZERO, "SUCC": SUCC, "ISZERO": ISZERO, "SHIFT": SHIFT, "PRED": PRED,
    "ADD": ADD, "SUB": SUB, "MUL": MUL,
    "LEQ": LEQ, "GEQ": GEQ, "LT": LT, "GT": GT, "EQ": EQ, "NEQ": NEQ,
    "Z": Z,
}
