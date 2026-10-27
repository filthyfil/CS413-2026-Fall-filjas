"""Demonstration programs, built directly as source ASTs.

Each example has an expected result kind and an explicit expected answer,
or DIVERGES when the expected outcome is step-budget exhaustion. The first
fourteen are the assignment's required demonstrations; the rest exercise
scope, laziness, and nested data. LOOP is (fix loop(x). loop x) 0.
"""
from __future__ import annotations

from dataclasses import dataclass

from observe import Kind
from source_ast import (
    d0exp,
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)

DIVERGES = "budget exhaustion"

N, T, F = D0Eint, D0Ebtf(True), D0Ebtf(False)
x, y, n = D0Evar("x"), D0Evar("y"), D0Evar("n")


def op(name: str, left: d0exp, right: d0exp) -> d0exp:
    return D0Eop2(name, left, right)


LOOP = D0Eapp(D0Efix("loop", "x", D0Eapp(D0Evar("loop"), x)), N(0))
FACT = D0Efix("fact", "n",
              D0Eif0(op("==", n, N(0)), N(1),
                     op("*", n, D0Eapp(D0Evar("fact"), op("-", n, N(1))))))
FIB = D0Efix("fib", "n",
             D0Eif0(op("<", n, N(2)), n,
                    op("+", D0Eapp(D0Evar("fib"), op("-", n, N(1))),
                       D0Eapp(D0Evar("fib"), op("-", n, N(2))))))


@dataclass(frozen=True)
class Example:
    label: str          # explanatory notation, not an input syntax
    source: d0exp
    kind: Kind
    expected: object    # int | bool | tuple, or DIVERGES
    required: bool = True


EXAMPLES: list[Example] = [
    Example("2 + 3 * 4", op("+", N(2), op("*", N(3), N(4))), "nat", 14),
    Example("2 - 5", op("-", N(2), N(5)), "nat", 0),
    Example("if 2 <= 3 then 7 else 9",
            D0Eif0(op("<=", N(2), N(3)), N(7), N(9)), "nat", 7),
    Example("let x = 3 in (lam y. x + y) 4",
            D0Elet("x", N(3), D0Eapp(D0Elam("y", op("+", x, y)), N(4))), "nat", 7),
    Example("fst (pair 2 true)", D0Epfst(D0Epair(N(2), T)), "nat", 2),
    Example("snd (pair 2 true)", D0Epsnd(D0Epair(N(2), T)), "bool", True),
    Example("(lam f. f 3) (lam x. x + 1)",
            D0Eapp(D0Elam("f", D0Eapp(D0Evar("f"), N(3))),
                   D0Elam("x", op("+", x, N(1)))), "nat", 4),
    Example("true and false", op("and", T, F), "bool", False),
    Example("false or true", op("or", F, T), "bool", True),
    Example("if true then 1 else LOOP", D0Eif0(T, N(1), LOOP), "nat", 1),
    Example("(lam x. 0) LOOP", D0Eapp(D0Elam("x", N(0)), LOOP), "nat", DIVERGES),
    Example("fact 4  (fix fact(n). if n == 0 then 1 else n * fact (n - 1))",
            D0Eapp(FACT, N(4)), "nat", 24),
    Example("fib 5  (fix fib(n). if n < 2 then n else fib (n-1) + fib (n-2))",
            D0Eapp(FIB, N(5)), "nat", 5),
    Example("LOOP", LOOP, "nat", DIVERGES),
    # Additional demonstrations.
    Example("pair (pair 2 true) 3",
            D0Epair(D0Epair(N(2), T), N(3)), (("nat", "bool"), "nat"), ((2, True), 3),
            required=False),
    Example("(fix f(f). f) 3", D0Eapp(D0Efix("f", "f", D0Evar("f")), N(3)), "nat", 3,
            required=False),
    Example("false and LOOP", op("and", F, LOOP), "bool", False, required=False),
    Example("not (3 != 3)", D0Eop1("not", op("!=", N(3), N(3))), "bool", True,
            required=False),
    Example("let s = 2 in let z = 3 in s * z   (encoding names as source names)",
            D0Elet("s", N(2), D0Elet("z", N(3), op("*", D0Evar("s"), D0Evar("z")))),
            "nat", 6, required=False),
    Example("let x = LOOP in 2", D0Elet("x", LOOP, N(2)), "nat", DIVERGES,
            required=False),
]
