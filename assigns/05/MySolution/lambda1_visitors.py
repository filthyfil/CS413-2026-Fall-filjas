"""Pretty-printing and capture-avoiding substitution visitors for lambda1_vp.py.

Requires Python 3.12 or later. The supplied interpreter is imported from the
parent directory and is not modified.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lambda1_vp import (  # noqa: E402
    D0ExpVisitor, d0exp, dvar, d0exp_fvset,
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)


class PrettyPrintVisitor(D0ExpVisitor[str]):
    """Render an expression as a single-line string without evaluating it.

    Every compound form is fully parenthesized, so no precedence rules are
    needed; each method formats one node and recurses through accept.
    """

    def visit_int(self, dexp: D0Eint) -> str:
        return str(dexp.arg1)

    def visit_btf(self, dexp: D0Ebtf) -> str:
        return "true" if dexp.arg1 else "false"

    def visit_var(self, dexp: D0Evar) -> str:
        return dexp.arg1

    def visit_op1(self, dexp: D0Eop1) -> str:
        return f"({dexp.name} {dexp.arg1.accept(self)})"

    def visit_op2(self, dexp: D0Eop2) -> str:
        return f"({dexp.arg1.accept(self)} {dexp.name} {dexp.arg2.accept(self)})"

    def visit_lam(self, dexp: D0Elam) -> str:
        return f"(lam {dexp.arg1}. {dexp.arg2.accept(self)})"

    def visit_fix(self, dexp: D0Efix) -> str:
        return f"(fix {dexp.arg1}({dexp.arg2}). {dexp.arg3.accept(self)})"

    def visit_app(self, dexp: D0Eapp) -> str:
        return f"({dexp.arg1.accept(self)} {dexp.arg2.accept(self)})"

    def visit_if0(self, dexp: D0Eif0) -> str:
        return (f"(if {dexp.arg1.accept(self)} then {dexp.arg2.accept(self)}"
                f" else {dexp.arg3.accept(self)})")

    def visit_let(self, dexp: D0Elet) -> str:
        return (f"(let {dexp.arg1} = {dexp.arg2.accept(self)}"
                f" in {dexp.arg3.accept(self)})")

    def visit_pair(self, dexp: D0Epair) -> str:
        return f"(pair {dexp.arg1.accept(self)} {dexp.arg2.accept(self)})"

    def visit_pfst(self, dexp: D0Epfst) -> str:
        return f"(fst {dexp.arg1.accept(self)})"

    def visit_psnd(self, dexp: D0Epsnd) -> str:
        return f"(snd {dexp.arg1.accept(self)})"


def d0exp_pretty(dexp: d0exp) -> str:
    """Return the single-line pretty-printed form of dexp."""
    return dexp.accept(PrettyPrintVisitor())


########################################################################
########################################################################
# Capture-avoiding substitution
########################################################################
########################################################################

class AllNamesVisitor(D0ExpVisitor[frozenset[dvar]]):
    """Collect every variable occurrence and every binder name, free or bound.

    Unlike FreeVariableVisitor, binders are added rather than removed, so the
    result is suitable for choosing names that collide with nothing.
    """

    def visit_int(self, dexp: D0Eint) -> frozenset[dvar]:
        return frozenset()

    def visit_btf(self, dexp: D0Ebtf) -> frozenset[dvar]:
        return frozenset()

    def visit_var(self, dexp: D0Evar) -> frozenset[dvar]:
        return frozenset({dexp.arg1})

    def visit_lam(self, dexp: D0Elam) -> frozenset[dvar]:
        return dexp.arg2.accept(self) | {dexp.arg1}

    def visit_fix(self, dexp: D0Efix) -> frozenset[dvar]:
        return dexp.arg3.accept(self) | {dexp.arg1, dexp.arg2}

    def visit_let(self, dexp: D0Elet) -> frozenset[dvar]:
        return dexp.arg2.accept(self) | dexp.arg3.accept(self) | {dexp.arg1}

    def visit_if0(self, dexp: D0Eif0) -> frozenset[dvar]:
        return (dexp.arg1.accept(self) | dexp.arg2.accept(self)
                | dexp.arg3.accept(self))

    def visit_op1(self, dexp: D0Eop1) -> frozenset[dvar]:
        return dexp.arg1.accept(self)

    def visit_pfst(self, dexp: D0Epfst) -> frozenset[dvar]:
        return dexp.arg1.accept(self)

    def visit_psnd(self, dexp: D0Epsnd) -> frozenset[dvar]:
        return dexp.arg1.accept(self)

    def visit_op2(self, dexp: D0Eop2) -> frozenset[dvar]:
        return dexp.arg1.accept(self) | dexp.arg2.accept(self)

    def visit_app(self, dexp: D0Eapp) -> frozenset[dvar]:
        return dexp.arg1.accept(self) | dexp.arg2.accept(self)

    def visit_pair(self, dexp: D0Epair) -> frozenset[dvar]:
        return dexp.arg1.accept(self) | dexp.arg2.accept(self)


def d0exp_names(dexp: d0exp) -> frozenset[dvar]:
    """Return every variable and binder name occurring anywhere in dexp."""
    return dexp.accept(AllNamesVisitor())


class FreshNames:
    """Deterministic fresh-name supply for one substitution call.

    fresh(base) returns base_1, base_2, ... -- the first candidate not in the
    used set -- and records it, so later requests never repeat it.
    """

    def __init__(self, used: frozenset[dvar]) -> None:
        self.used = set(used)

    def fresh(self, base: dvar) -> dvar:
        k = 1
        while f"{base}_{k}" in self.used:
            k += 1
        name = f"{base}_{k}"
        self.used.add(name)
        return name


class SubstitutionVisitor(D0ExpVisitor[d0exp]):
    """Compute dexp[target := replacement], renaming binders to avoid capture.

    The visitor carries the target, the replacement, the replacement's free
    variables, and a shared fresh-name supply. Alpha-renaming a binder y to z
    is itself a substitution body[y := z], run by a new visitor that shares the
    same supply; since z is fresh it can never trigger further renaming, and
    because it is a real substitution it stops at nested binders that shadow y.
    Input trees are never mutated; unchanged subtrees may be reused.
    """

    def __init__(self, target: dvar, replacement: d0exp,
                 names: FreshNames) -> None:
        self.target = target
        self.replacement = replacement
        self.replacement_fv = d0exp_fvset(replacement)
        self.names = names

    def _rename(self, body: d0exp, old: dvar, new: dvar) -> d0exp:
        return body.accept(SubstitutionVisitor(old, D0Evar(new), self.names))

    def _affects(self, body: d0exp) -> bool:
        # Substitution can change body only if the target occurs free in it.
        return self.target in d0exp_fvset(body)

    def _bind(self, name: dvar, body: d0exp) -> tuple[dvar, d0exp]:
        """Substitute under a single binder (lambda parameter, let name)."""
        if name == self.target or not self._affects(body):
            return name, body
        if name in self.replacement_fv:
            new = self.names.fresh(name)
            body, name = self._rename(body, name, new), new
        return name, body.accept(self)

    def visit_int(self, dexp: D0Eint) -> d0exp:
        return D0Eint(dexp.arg1)

    def visit_btf(self, dexp: D0Ebtf) -> d0exp:
        return D0Ebtf(dexp.arg1)

    def visit_var(self, dexp: D0Evar) -> d0exp:
        if dexp.arg1 == self.target:
            return self.replacement
        return D0Evar(dexp.arg1)

    def visit_lam(self, dexp: D0Elam) -> d0exp:
        name, body = self._bind(dexp.arg1, dexp.arg2)
        return D0Elam(name, body)

    def visit_let(self, dexp: D0Elet) -> d0exp:
        # The initializer is outside the let's scope: always substitute there.
        init = dexp.arg2.accept(self)
        name, body = self._bind(dexp.arg1, dexp.arg3)
        return D0Elet(name, init, body)

    def visit_fix(self, dexp: D0Efix) -> d0exp:
        fname, param, body = dexp.arg1, dexp.arg2, dexp.arg3
        if self.target in (fname, param) or not self._affects(body):
            return D0Efix(fname, param, body)
        if fname == param:
            # The parameter shadows the function name, so every occurrence in
            # body refers to the parameter. Rename both binders apart: renaming
            # only the parameter would unshadow fname and let it capture.
            if param in self.replacement_fv:
                new_param = self.names.fresh(param)
                body = self._rename(body, param, new_param)
                fname, param = self.names.fresh(fname), new_param
        else:
            if fname in self.replacement_fv:
                new_fname = self.names.fresh(fname)
                body, fname = self._rename(body, fname, new_fname), new_fname
            if param in self.replacement_fv:
                new_param = self.names.fresh(param)
                body, param = self._rename(body, param, new_param), new_param
        return D0Efix(fname, param, body.accept(self))

    def visit_app(self, dexp: D0Eapp) -> d0exp:
        return D0Eapp(dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_if0(self, dexp: D0Eif0) -> d0exp:
        return D0Eif0(dexp.arg1.accept(self), dexp.arg2.accept(self),
                      dexp.arg3.accept(self))

    def visit_op1(self, dexp: D0Eop1) -> d0exp:
        return D0Eop1(dexp.name, dexp.arg1.accept(self))

    def visit_op2(self, dexp: D0Eop2) -> d0exp:
        return D0Eop2(dexp.name, dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_pair(self, dexp: D0Epair) -> d0exp:
        return D0Epair(dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_pfst(self, dexp: D0Epfst) -> d0exp:
        return D0Epfst(dexp.arg1.accept(self))

    def visit_psnd(self, dexp: D0Epsnd) -> d0exp:
        return D0Epsnd(dexp.arg1.accept(self))


def d0exp_substitute(dexp: d0exp, variable: dvar, replacement: d0exp) -> d0exp:
    """Return dexp[variable := replacement] without capturing free names.

    Fresh names avoid every name in dexp and replacement, the target, and any
    name generated earlier in this call.
    """
    used = d0exp_names(dexp) | d0exp_names(replacement) | {variable}
    return dexp.accept(SubstitutionVisitor(variable, replacement, FreshNames(used)))


########################################################################
########################################################################
# Alpha-equivalence via De Bruijn indices
########################################################################
########################################################################

class DeBruijnVisitor(D0ExpVisitor[tuple]):
    """Translate an expression to a nameless tuple form.

    A bound variable becomes ("bound", k), where k counts the binders between
    the occurrence and the one that introduces it (0 = innermost). Free
    variables keep their names. The scope is a tuple of binder names,
    innermost first; entering a binder creates a new visitor, as in
    EvaluateVisitor. Alpha-equivalent expressions translate to equal tuples.
    """

    def __init__(self, scope: tuple[dvar, ...] = ()) -> None:
        self.scope = scope

    def _under(self, binders: tuple[dvar, ...], body: d0exp) -> tuple:
        # binders are listed innermost first.
        return body.accept(DeBruijnVisitor(binders + self.scope))

    def visit_int(self, dexp: D0Eint) -> tuple:
        return ("int", dexp.arg1)

    def visit_btf(self, dexp: D0Ebtf) -> tuple:
        return ("btf", dexp.arg1)

    def visit_var(self, dexp: D0Evar) -> tuple:
        if dexp.arg1 in self.scope:
            # index() finds the innermost binder, which handles shadowing.
            return ("bound", self.scope.index(dexp.arg1))
        return ("free", dexp.arg1)

    def visit_lam(self, dexp: D0Elam) -> tuple:
        return ("lam", self._under((dexp.arg1,), dexp.arg2))

    def visit_fix(self, dexp: D0Efix) -> tuple:
        # The parameter is the inner binder, so it shadows the function name.
        return ("fix", self._under((dexp.arg2, dexp.arg1), dexp.arg3))

    def visit_let(self, dexp: D0Elet) -> tuple:
        return ("let", dexp.arg2.accept(self), self._under((dexp.arg1,), dexp.arg3))

    def visit_app(self, dexp: D0Eapp) -> tuple:
        return ("app", dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_if0(self, dexp: D0Eif0) -> tuple:
        return ("if0", dexp.arg1.accept(self), dexp.arg2.accept(self),
                dexp.arg3.accept(self))

    def visit_op1(self, dexp: D0Eop1) -> tuple:
        return ("op1", dexp.name, dexp.arg1.accept(self))

    def visit_op2(self, dexp: D0Eop2) -> tuple:
        return ("op2", dexp.name, dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_pair(self, dexp: D0Epair) -> tuple:
        return ("pair", dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_pfst(self, dexp: D0Epfst) -> tuple:
        return ("fst", dexp.arg1.accept(self))

    def visit_psnd(self, dexp: D0Epsnd) -> tuple:
        return ("snd", dexp.arg1.accept(self))


def d0exp_debruijn(dexp: d0exp) -> tuple:
    """Return the nameless (De Bruijn) form of dexp."""
    return dexp.accept(DeBruijnVisitor())


def d0exp_alpha_equiv(dexp1: d0exp, dexp2: d0exp) -> bool:
    """Return whether dexp1 and dexp2 differ only by consistent bound renaming."""
    return d0exp_debruijn(dexp1) == d0exp_debruijn(dexp2)
