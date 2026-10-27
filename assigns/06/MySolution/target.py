"""Target language: Church's pure, untyped lambda-calculus.

    Term ::= Var(name) | Lam(name, Term) | App(Term, Term)

This AST is separate from the source AST. Nodes are frozen, so no operation
here can mutate an input term; operations return new terms and may share
unchanged subterms. Names follow the source identifier convention
[A-Za-z_][A-Za-z0-9_]*.

The substitution and alpha-equivalence algorithms are ported from my
Assignment 5 SubstitutionVisitor and DeBruijnVisitor (assigns/05/MySolution/
lambda1_visitors.py), reduced to the three target forms.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from source_visitors import FreshNames

type Name = str


@dataclass(frozen=True)
class Var:
    name: Name

    @cached_property
    def fv(self) -> frozenset[Name]:
        return frozenset({self.name})


@dataclass(frozen=True)
class Lam:
    param: Name
    body: Term

    @cached_property
    def fv(self) -> frozenset[Name]:
        return self.body.fv - {self.param}


@dataclass(frozen=True)
class App:
    fn: Term
    arg: Term

    @cached_property
    def fv(self) -> frozenset[Name]:
        return self.fn.fv | self.arg.fv


type Term = Var | Lam | App
# Free-variable sets are cached per node: the reducer substitutes repeatedly
# into the same subterms, and frozen nodes make the cache safe.


########################################################################
# Printing
########################################################################

def term_print(term: Term) -> str:
    """Render x, (lam x. body), and (fn arg), recursively."""
    match term:
        case Var(x):
            return x
        case Lam(x, body):
            return f"(lam {x}. {term_print(body)})"
        case App(fn, arg):
            return f"({term_print(fn)} {term_print(arg)})"
    raise TypeError(f"not a target term: {term!r}")


########################################################################
# Names
########################################################################

def free_vars(term: Term) -> frozenset[Name]:
    """Return the free variables of term."""
    return term.fv


def all_names(term: Term) -> frozenset[Name]:
    """Return every variable occurrence and binder name, free or bound."""
    match term:
        case Var(x):
            return frozenset({x})
        case Lam(x, body):
            return all_names(body) | {x}
        case App(fn, arg):
            return all_names(fn) | all_names(arg)
    raise TypeError(f"not a target term: {term!r}")


def is_pure(term: object) -> bool:
    """Return whether term is built only from Var, Lam, and App nodes."""
    match term:
        case Var(x):
            return isinstance(x, str)
        case Lam(x, body):
            return isinstance(x, str) and is_pure(body)
        case App(fn, arg):
            return is_pure(fn) and is_pure(arg)
    return False


########################################################################
# Capture-avoiding substitution
########################################################################

def substitute(term: Term, variable: Name, replacement: Term) -> Term:
    """Return term[variable := replacement] without capturing free names.

    A binder is renamed only when it would capture a free variable of the
    replacement. Fresh names come from FreshNames (base_1, base_2, ...) and
    avoid every name in term and replacement and the target variable. For a
    closed replacement -- the only case the closed-term reducer produces --
    no renaming can happen, so the name supply is never built.
    """
    rfv = replacement.fv
    names = (FreshNames(all_names(term) | all_names(replacement) | {variable})
             if rfv else None)
    return _subst(term, variable, replacement, rfv, names)


def _subst(term: Term, x: Name, r: Term, rfv: frozenset[Name],
           names: FreshNames | None) -> Term:
    if x not in term.fv:
        # Covers Var(y) with y != x and any binder that shadows x.
        return term
    match term:
        case Var():
            return r
        case App(fn, arg):
            return App(_subst(fn, x, r, rfv, names), _subst(arg, x, r, rfv, names))
        case Lam(p, body):
            # p != x here, since x is free in term.
            if p in rfv:
                assert names is not None
                new = names.fresh(p)
                body = _subst(body, p, Var(new), frozenset({new}), names)
                p = new
            return Lam(p, _subst(body, x, r, rfv, names))
    raise TypeError(f"not a target term: {term!r}")


########################################################################
# Alpha-equivalence via De Bruijn indices
########################################################################

def debruijn(term: Term, scope: tuple[Name, ...] = ()) -> tuple:
    """Return a nameless form: bound variables become ("bound", k), where
    k = 0 is the innermost binder; free variables keep their names."""
    match term:
        case Var(x):
            if x in scope:
                return ("bound", scope.index(x))
            return ("free", x)
        case Lam(x, body):
            return ("lam", debruijn(body, (x,) + scope))
        case App(fn, arg):
            return ("app", debruijn(fn, scope), debruijn(arg, scope))
    raise TypeError(f"not a target term: {term!r}")


def alpha_equiv(term1: Term, term2: Term) -> bool:
    """Return whether the terms differ only by consistent bound renaming."""
    return debruijn(term1) == debruijn(term2)
