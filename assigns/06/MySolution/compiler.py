"""Compiler from extended LAMBDA source ASTs to pure lambda terms.

compile_expr(e) returns C[e], a target term built only from Var, Lam, and
App. CompileVisitor implements D0ExpVisitor, so dispatch goes through the
supplied accept methods. Each visit method compiles the node's children and
combines their translations; nothing is evaluated, so even a diverging
program compiles. This module does not import the evaluator.

Translation rules (OP names are closed combinators from church.py, expanded
in place as pure terms):

    C[n]                    = NUM(n)                         n >= 0
    C[true] / C[false]      = TRUE / FALSE
    C[x]                    = x
    C[lam x. e]             = lam x. C[e]
    C[e1 e2]                = C[e1] C[e2]
    C[not e]                = NOT C[e]
    C[e1 op e2]             = OP C[e1] C[e2]
        + - * < <= > >= == !=  ->  ADD SUB MUL LT LEQ GT GEQ EQ NEQ
    C[e1 and e2]            = (C[e1] (lam u. C[e2]) (lam v. FALSE)) I
    C[e1 or e2]             = (C[e1] (lam u. TRUE) (lam v. C[e2])) I
    C[if c then t else f]   = (C[c] (lam u. C[t]) (lam v. C[f])) I
    C[let x = e1 in e2]     = (lam x. C[e2]) C[e1]
    C[pair e1 e2]           = PAIR C[e1] C[e2]
    C[fst e] / C[snd e]     = FST C[e] / SND C[e]
    C[fix f(x). e]          = Z (lam f. lam x. C[e])

Call-by-value evaluates OP C[e1] C[e2] and PAIR C[e1] C[e2] left to right:
the combinator is a value, then C[e1], then the partial application, then
C[e2]. Source binders keep their names, so lexical scope carries over
unchanged; for fix f(f). e the target lam f. lam f. C[e] gives the inner
(parameter) binder precedence, as the source requires.

Fresh-name policy: the only binders the compiler introduces around
translated terms are the thunk parameters u and v. For a thunk lam u. T,
the parameter is the first of u_1, u_2, ... (v_1, v_2, ... for v) that does
not occur anywhere in T -- free or bound, including source free variables.
The choice depends only on T, so it is deterministic and compositional, and
the unused parameter cannot capture anything. No source name is reserved.
Library combinators are closed and are only ever applied, never wrapped
around translated terms, so their internal binder names cannot capture.
Hence FV(C[e]) = FV(e).

Unsupported input -- negative literals, operators outside the language,
malformed identifiers -- raises CompileError. Every node is visited, so this
includes unselected branches and unapplied function bodies.
"""
from __future__ import annotations

import re

from church import (
    app, num, I, TRUE, FALSE, NOT, PAIR, FST, SND, Z,
    ADD, SUB, MUL, LT, LEQ, GT, GEQ, EQ, NEQ,
)
from source_ast import (
    D0ExpVisitor, d0exp,
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)
from source_visitors import FreshNames, d0exp_pretty
from target import Var, Lam, App, Term, all_names

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

BINARY: dict[str, Term] = {
    "+": ADD, "-": SUB, "*": MUL,
    "<": LT, "<=": LEQ, ">": GT, ">=": GEQ, "==": EQ, "!=": NEQ,
}
UNARY: dict[str, Term] = {"not": NOT}
SHORT_CIRCUIT = ("and", "or")


class CompileError(ValueError):
    """Raised for source input outside the project's language."""


def thunk(base: str, body: Term) -> Lam:
    """lam p. body, with p fresh against every name in body."""
    return Lam(FreshNames(all_names(body)).fresh(base), body)


def select(cond: Term, then: Term, other: Term) -> Term:
    """(cond (lam u. then) (lam v. other)) I: force only the chosen branch."""
    return App(app(cond, thunk("u", then), thunk("v", other)), I)


class CompileVisitor(D0ExpVisitor[Term]):
    """Translate one source node by combining its children's translations."""

    def visit_int(self, dexp: D0Eint) -> Term:
        n = dexp.arg1
        if n < 0:
            raise CompileError(f"negative literal {n} is outside the source language")
        return num(n)

    def visit_btf(self, dexp: D0Ebtf) -> Term:
        return TRUE if dexp.arg1 else FALSE

    def visit_var(self, dexp: D0Evar) -> Term:
        return Var(_name(dexp.arg1))

    def visit_lam(self, dexp: D0Elam) -> Term:
        return Lam(_name(dexp.arg1), dexp.arg2.accept(self))

    def visit_app(self, dexp: D0Eapp) -> Term:
        return App(dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_op1(self, dexp: D0Eop1) -> Term:
        if dexp.name not in UNARY:
            raise CompileError(f"unsupported unary operator {dexp.name!r} "
                               f"in {d0exp_pretty(dexp)}")
        return App(UNARY[dexp.name], dexp.arg1.accept(self))

    def visit_op2(self, dexp: D0Eop2) -> Term:
        name = dexp.name
        if name not in BINARY and name not in SHORT_CIRCUIT:
            raise CompileError(f"unsupported binary operator {name!r} "
                               f"in {d0exp_pretty(dexp)}")
        left, right = dexp.arg1.accept(self), dexp.arg2.accept(self)
        if name == "and":
            return select(left, right, FALSE)
        if name == "or":
            return select(left, TRUE, right)
        return app(BINARY[name], left, right)

    def visit_if0(self, dexp: D0Eif0) -> Term:
        return select(dexp.arg1.accept(self), dexp.arg2.accept(self),
                      dexp.arg3.accept(self))

    def visit_let(self, dexp: D0Elet) -> Term:
        init = dexp.arg2.accept(self)
        return App(Lam(_name(dexp.arg1), dexp.arg3.accept(self)), init)

    def visit_pair(self, dexp: D0Epair) -> Term:
        return app(PAIR, dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_pfst(self, dexp: D0Epfst) -> Term:
        return App(FST, dexp.arg1.accept(self))

    def visit_psnd(self, dexp: D0Epsnd) -> Term:
        return App(SND, dexp.arg1.accept(self))

    def visit_fix(self, dexp: D0Efix) -> Term:
        fname, param = _name(dexp.arg1), _name(dexp.arg2)
        return App(Z, Lam(fname, Lam(param, dexp.arg3.accept(self))))


def _name(x: str) -> str:
    if not isinstance(x, str) or not _IDENT.fullmatch(x):
        raise CompileError(f"invalid identifier {x!r}")
    return x


def compile_expr(dexp: d0exp) -> Term:
    """Return the pure lambda term C[dexp]. The input is not modified."""
    return dexp.accept(CompileVisitor())
