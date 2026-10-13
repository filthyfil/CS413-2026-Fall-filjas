"""Example inputs and expected results shared by both test suites.

Expected substitution results use the documented fresh-name policy (base_1,
base_2, ...). ALPHA_CASES restate some results with hand-picked bound names,
to be compared up to alpha-equivalence instead of exactly.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from lambda1_vp import (  # noqa: E402
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)

########################################################################
# Constructor shorthands
########################################################################

I, B, V = D0Eint, D0Ebtf, D0Evar
op1, op2 = D0Eop1, D0Eop2
lam, fix, app, if0, let = D0Elam, D0Efix, D0Eapp, D0Eif0, D0Elet
pair, fst, snd = D0Epair, D0Epfst, D0Epsnd


def add(a, b):
    return op2("+", a, b)


OPS2 = ["+", "-", "*", "/", "<", ">", "<=", ">=", "==", "!="]

########################################################################
# Pretty printing: (name, expression, expected string)
########################################################################

PRETTY_CASES = [
    ("int", I(42), "42"),
    ("int zero", I(0), "0"),
    ("int negative", I(-7), "-7"),
    ("int large", I(10**40), "1" + "0" * 40),
    ("int large negative", I(-(10**25)), "-1" + "0" * 25),
    ("btf true", B(True), "true"),
    ("btf false", B(False), "false"),
    ("var", V("x_1"), "x_1"),
    ("op1 +1", op1("+1", V("x")), "(+1 x)"),
    ("op1 -1 negative", op1("-1", I(-3)), "(-1 -3)"),
    *[(f"op2 {o}", op2(o, V("a"), I(2)), f"(a {o} 2)") for o in OPS2],
    ("lam", lam("x", V("x")), "(lam x. x)"),
    ("fix", fix("f", "n", app(V("f"), V("n"))), "(fix f(n). (f n))"),
    ("app", app(V("f"), I(1)), "(f 1)"),
    ("if0", if0(B(True), I(1), I(2)), "(if true then 1 else 2)"),
    ("let", let("x", I(1), add(V("x"), V("x"))), "(let x = 1 in (x + x))"),
    ("pair", pair(I(1), B(False)), "(pair 1 false)"),
    ("fst", fst(pair(I(1), I(2))), "(fst (pair 1 2))"),
    ("snd", snd(V("p")), "(snd p)"),
    ("spec example", app(lam("x", add(V("x"), I(1))), I(4)),
     "((lam x. (x + 1)) 4)"),
    ("division by zero not evaluated", op2("/", I(1), I(0)), "(1 / 0)"),
    ("nested factorial",
     fix("fact", "n", if0(op2("<=", V("n"), I(0)), I(1),
                          op2("*", V("n"),
                              app(V("fact"), op1("-1", V("n")))))),
     "(fix fact(n). (if (n <= 0) then 1 else (n * (fact (-1 n)))))"),
    ("nested let and projections",
     let("p", pair(I(-5), B(False)), fst(snd(V("p")))),
     "(let p = (pair -5 false) in (fst (snd p)))"),
    ("nested curried application",
     app(app(lam("x", lam("y", V("x"))), I(1)), I(2)),
     "(((lam x. (lam y. x)) 1) 2)"),
]

########################################################################
# Substitution: (name, expression, target, replacement, expected)
########################################################################

# 2. Every constructor, matching and nonmatching variables, and replacements
#    that contain the target.
CONSTRUCTOR_CASES = [
    ("int", I(5), "x", V("y"), I(5)),
    ("btf", B(True), "x", V("y"), B(True)),
    ("var matching", V("x"), "x", I(3), I(3)),
    ("var nonmatching", V("z"), "x", I(3), V("z")),
    ("op1", op1("+1", V("x")), "x", I(3), op1("+1", I(3))),
    ("op2", add(V("x"), V("z")), "x", I(3), add(I(3), V("z"))),
    ("lam body", lam("y", add(V("x"), V("y"))), "x", I(3),
     lam("y", add(I(3), V("y")))),
    ("fix body", fix("f", "n", add(V("x"), app(V("f"), V("n")))), "x", I(3),
     fix("f", "n", add(I(3), app(V("f"), V("n"))))),
    ("app", app(V("x"), V("x")), "x", V("g"), app(V("g"), V("g"))),
    ("if0", if0(V("x"), V("x"), V("z")), "x", B(True),
     if0(B(True), B(True), V("z"))),
    ("let init and body", let("y", V("x"), add(V("x"), V("y"))), "x", I(3),
     let("y", I(3), add(I(3), V("y")))),
    ("pair", pair(V("x"), V("y")), "x", I(1), pair(I(1), V("y"))),
    ("fst", fst(V("x")), "x", pair(I(1), I(2)), fst(pair(I(1), I(2)))),
    ("snd", snd(V("x")), "x", pair(I(1), I(2)), snd(pair(I(1), I(2)))),
    ("replacement contains target", V("x"), "x", add(V("x"), I(1)),
     add(V("x"), I(1))),
    ("replacement contains target, not resubstituted",
     add(V("x"), V("x")), "x", add(V("x"), I(1)),
     add(add(V("x"), I(1)), add(V("x"), I(1)))),
]

# 3. Shadowing: the target is bound, so that region is left alone.
SHADOWING_CASES = [
    ("lam shadows", lam("x", add(V("x"), V("y"))), "x", I(3),
     lam("x", add(V("x"), V("y")))),
    ("fix name shadows", fix("x", "n", app(V("x"), V("n"))), "x", I(3),
     fix("x", "n", app(V("x"), V("n")))),
    ("fix param shadows", fix("f", "x", app(V("f"), V("x"))), "x", I(3),
     fix("f", "x", app(V("f"), V("x")))),
    ("fix name equals param, shadows", fix("g", "g", add(V("g"), I(1))),
     "g", I(3), fix("g", "g", add(V("g"), I(1)))),
    ("let shadows body only", let("x", V("x"), add(V("x"), V("y"))), "x", I(3),
     let("x", I(3), add(V("x"), V("y")))),
    ("inner lam shadows", lam("y", add(V("x"), lam("x", V("x")))), "x", I(3),
     lam("y", add(I(3), lam("x", V("x"))))),
]

# 4. Capture avoidance at each kind of binder.
CAPTURE_CASES = [
    ("lam capture", lam("y", add(V("x"), V("y"))), "x", V("y"),
     lam("y_1", add(V("y"), V("y_1")))),
    ("let capture", let("y", V("x"), add(V("x"), V("y"))), "x", V("y"),
     let("y_1", V("y"), add(V("y"), V("y_1")))),
    ("fix name capture", fix("f", "n", add(V("x"), app(V("f"), V("n")))),
     "x", V("f"),
     fix("f_1", "n", add(V("f"), app(V("f_1"), V("n"))))),
    ("fix param capture", fix("f", "n", add(V("x"), app(V("f"), V("n")))),
     "x", V("n"),
     fix("f", "n_1", add(V("n"), app(V("f"), V("n_1"))))),
    ("fix both binders capture",
     fix("f", "n", add(V("x"), app(V("f"), V("n")))),
     "x", add(V("f"), V("n")),
     fix("f_1", "n_1", add(add(V("f"), V("n")), app(V("f_1"), V("n_1"))))),
    ("fix name equals param, capture", fix("f", "f", add(V("x"), V("f"))),
     "x", V("f"),
     fix("f_2", "f_1", add(V("f"), V("f_1")))),
]

# 5. Nested shadowing during renaming, and fresh-name collisions.
RENAMING_CASES = [
    ("nested lam shadowing during rename",
     lam("y", add(add(V("x"), V("y")), lam("y", V("y")))), "x", V("y"),
     lam("y_1", add(add(V("y"), V("y_1")), lam("y", V("y"))))),
    ("nested let shadowing during rename",
     lam("y", add(V("x"), let("y", V("y"), V("y")))), "x", V("y"),
     lam("y_1", add(V("y"), let("y", V("y_1"), V("y"))))),
    ("nested fix shadowing during rename",
     lam("f", add(V("x"), fix("f", "n", app(V("f"), V("n"))))), "x", V("f"),
     lam("f_1", add(V("f"), fix("f", "n", app(V("f"), V("n")))))),
    ("fresh avoids existing bound name",
     lam("y", add(V("x"), lam("y_1", add(V("y"), V("y_1"))))), "x", V("y"),
     lam("y_2", add(V("y"), lam("y_1", add(V("y_2"), V("y_1")))))),
    ("fresh avoids existing free name",
     lam("y", add(add(V("x"), V("y")), V("y_1"))), "x", V("y"),
     lam("y_2", add(add(V("y"), V("y_2")), V("y_1")))),
    ("fresh avoids names in replacement",
     lam("y", add(V("x"), V("y"))), "x", add(V("y"), V("y_1")),
     lam("y_2", add(add(V("y"), V("y_1")), V("y_2")))),
    ("fresh avoids names generated earlier, siblings",
     pair(lam("y", add(V("x"), V("y"))), lam("y", add(V("x"), V("y")))),
     "x", V("y"),
     pair(lam("y_1", add(V("y"), V("y_1"))),
          lam("y_2", add(V("y"), V("y_2"))))),
    ("fresh avoids names generated earlier, nested",
     lam("y", lam("y", add(V("x"), V("y")))), "x", V("y"),
     lam("y_1", lam("y_2", add(V("y"), V("y_2"))))),
    ("no renaming when target absent from scope",
     lam("y", V("y")), "x", V("y"), lam("y", V("y"))),
]

# 6. A let initializer is outside the let's scope; its body is inside.
LET_CASES = [
    ("let same name: init substituted, body not",
     let("x", V("x"), V("x")), "x", I(3), let("x", I(3), V("x"))),
    ("let other name: init and body substituted",
     let("y", V("x"), V("x")), "x", I(3), let("y", I(3), I(3))),
    ("let rename affects body only",
     let("y", add(V("y"), V("x")), add(V("x"), V("y"))), "x", V("y"),
     let("y_1", add(V("y"), V("y")), add(V("y"), V("y_1")))),
    ("let target only in init: no rename",
     let("y", V("x"), V("y")), "x", V("y"), let("y", V("y"), V("y"))),
]

SUBST_CASES = (CONSTRUCTOR_CASES + SHADOWING_CASES + CAPTURE_CASES
               + RENAMING_CASES + LET_CASES)

# Results restated with different bound names: equal up to alpha only.
ALPHA_CASES = [
    ("lam capture", lam("y", add(V("x"), V("y"))), "x", V("y"),
     lam("z", add(V("y"), V("z")))),
    ("fix both binders capture",
     fix("f", "n", add(V("x"), app(V("f"), V("n")))), "x", add(V("f"), V("n")),
     fix("g", "m", add(add(V("f"), V("n")), app(V("g"), V("m"))))),
    ("fix name equals param, capture", fix("f", "f", add(V("x"), V("f"))),
     "x", V("f"), fix("h", "k", add(V("f"), V("k")))),
    ("nested lam shadowing during rename",
     lam("y", add(add(V("x"), V("y")), lam("y", V("y")))), "x", V("y"),
     lam("w", add(add(V("y"), V("w")), lam("q", V("q"))))),
]

########################################################################
# Alpha-equivalence checker: (name, left, right, equivalent?)
########################################################################

ALPHA_EQUIV_CASES = [
    ("identity renamed", lam("x", V("x")), lam("y", V("y")), True),
    ("constant vs identity", lam("x", V("y")), lam("y", V("y")), False),
    ("free names differ", V("x"), V("y"), False),
    ("fix renamed", fix("f", "n", app(V("f"), V("n"))),
     fix("g", "m", app(V("g"), V("m"))), True),
    ("fix name vs param", fix("f", "n", V("f")), fix("f", "n", V("n")), False),
    ("fix name equals param refers to param", fix("f", "f", V("f")),
     fix("g", "h", V("h")), True),
    ("fix name equals param is not name", fix("f", "f", V("f")),
     fix("g", "h", V("g")), False),
    ("let renamed", let("x", V("x"), V("x")), let("y", V("x"), V("y")), True),
    ("let init is outside scope", let("x", V("x"), V("x")),
     let("y", V("y"), V("y")), False),
    ("int vs btf", I(1), B(True), False),
    ("captured result is not equivalent", lam("y", add(V("y"), V("y"))),
     lam("z", add(V("y"), V("z"))), False),
]

########################################################################
# Expressions that would raise if they were evaluated.
########################################################################

UNEVALUABLE = [
    op2("/", V("x"), I(0)),                 # division by zero
    add(B(True), V("x")),                   # operand type error
    op1("bogus", V("x")),                   # unsupported operator
    if0(I(5), V("x"), V("x")),              # non-boolean condition
    app(I(1), V("x")),                      # applying a non-function
    fst(V("x")),                            # projection of a non-pair
]
