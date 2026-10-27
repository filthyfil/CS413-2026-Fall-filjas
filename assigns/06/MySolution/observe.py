"""Bounded observers that decode target values as naturals, booleans, pairs.

A returned lambda may contain unevaluated redexes under its binders, so
results are not matched against normal-form numerals. Instead each observer
applies the value to a pure target observation context, runs that with the
shared call-by-value evaluator under an observation budget, and inspects
only the final shape in Python. The caller supplies the expected kind:
NUM(0) and FALSE are the same lambda term.

Natural: evaluate  value STEP BASE  where

    STEP = lam tail. lam c. lam z. c tail
    BASE = lam c. lam z. z

A numeral applies STEP n times to BASE; call-by-value evaluates each STEP
application to a value, so the result is a finite spine

    lam c. lam z. c (lam c. lam z. c ( ... (lam c. lam z. z)))

with n "c tail" nodes, counted structurally up to alpha-renaming.

Boolean: evaluate  value MARK_T MARK_F  with two distinct closed markers

    MARK_T = lam p. lam q. lam r. p        MARK_F = lam p. lam q. lam r. q

the result must be alpha-equivalent to exactly one of them. Applying either
marker to anything yields a two-binder lambda, which matches neither, so a
value that uses a marker as a function (e.g. NUM(2)) is rejected as
malformed instead of happening to land on the other marker.

Pair: the pair is already a value; evaluate  FST pair  and  SND pair  as
target terms under the observation budget, then observe each component
with its expected kind, recursively for nested pairs.

Outcomes: DECODED (with the Python value), EXHAUSTED (the observation
budget ran out), or MALFORMED (the final shape is not a valid encoding of
the expected kind). steps is the total number of beta-value steps spent on
observation, reported separately from execution steps. Python never
performs the encoded arithmetic: it only counts spine nodes and compares
marker shapes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, Union

from church import lam, app, FST, SND
from evaluator import reduce_term
from target import Var, Lam, App, Term, alpha_equiv

DECODED: Final = "decoded"
EXHAUSTED: Final = "exhausted"
MALFORMED: Final = "malformed"

type Kind = Union[Literal["nat", "bool"], tuple["Kind", "Kind"]]

STEP = lam("tail", "c", "z", app(Var("c"), Var("tail")))
BASE = lam("c", "z", Var("z"))
MARK_T = lam("p", "q", "r", Var("p"))
MARK_F = lam("p", "q", "r", Var("q"))


@dataclass(frozen=True)
class Observation:
    status: Literal["decoded", "exhausted", "malformed"]
    value: int | bool | tuple | None
    steps: int
    detail: str = ""

    @property
    def decoded(self) -> bool:
        return self.status == DECODED


def observe(value: Term, kind: Kind, budget: int) -> Observation:
    """Decode a target value as the expected kind within budget steps."""
    if not isinstance(value, Lam):
        raise TypeError("observe expects a target value (a lambda abstraction)")
    if kind == "nat":
        return _observe_nat(value, budget)
    if kind == "bool":
        return _observe_bool(value, budget)
    if isinstance(kind, tuple) and len(kind) == 2:
        return _observe_pair(value, kind, budget)
    raise ValueError(f"unknown result kind {kind!r}")


def _observe_nat(value: Lam, budget: int) -> Observation:
    result = reduce_term(app(value, STEP, BASE), budget)
    if not result.completed:
        return Observation(EXHAUSTED, None, result.steps)
    count = _count_spine(result.term)
    if count is None:
        return Observation(MALFORMED, None, result.steps,
                           "observation did not produce a STEP/BASE spine")
    return Observation(DECODED, count, result.steps)


def _count_spine(term: Term) -> int | None:
    """Count "lam c. lam z. c tail" nodes down to "lam c. lam z. z"."""
    count = 0
    while True:
        match term:
            case Lam(c, Lam(z, App(Var(head), tail))) if head == c != z:
                count += 1
                term = tail
            case Lam(c, Lam(z, Var(bottom))) if bottom == z:
                return count
            case _:
                return None


def _observe_bool(value: Lam, budget: int) -> Observation:
    result = reduce_term(app(value, MARK_T, MARK_F), budget)
    if not result.completed:
        return Observation(EXHAUSTED, None, result.steps)
    if alpha_equiv(result.term, MARK_T):
        return Observation(DECODED, True, result.steps)
    if alpha_equiv(result.term, MARK_F):
        return Observation(DECODED, False, result.steps)
    return Observation(MALFORMED, None, result.steps,
                       "observation did not select a boolean marker")


def _observe_pair(value: Lam, kinds: tuple[Kind, Kind], budget: int) -> Observation:
    parts, used = [], 0
    for projection, kind in ((FST, kinds[0]), (SND, kinds[1])):
        projected = reduce_term(App(projection, value), budget - used)
        used += projected.steps
        if not projected.completed:
            return Observation(EXHAUSTED, None, used)
        part = observe(projected.term, kind, budget - used)
        used += part.steps
        if not part.decoded:
            return Observation(part.status, None, used, part.detail)
        parts.append(part.value)
    return Observation(DECODED, tuple(parts), used)
