"""Shared evaluator for source ASTs and target terms.

One machine evaluates both languages with weak, left-to-right call-by-value.
It walks the program with an explicit stack of evaluation-context frames
(iterative, so long runs cannot overflow Python's call stack). Variables,
abstractions, and applications are handled by the same cases for both ASTs:
an application evaluates its function, then its argument, then performs one
beta-value step

    (lam x. body) v  -->  body[x := v]

by capture-avoiding substitution (target.substitute for target terms,
source_visitors.d0exp_substitute for source ASTs). Source-only constructors
push their own frames and follow the source-language rules:

- Literals: naturals n >= 0 and booleans are values; a negative literal is
  an error. Lambdas and fix functions are values; a pair of values is a value.
- Operators evaluate operands left to right. "-" is truncated subtraction.
  Comparisons take naturals; "not" takes a boolean.
- "and" / "or" short-circuit: the right operand is evaluated only when the
  left is true / false, respectively.
- if evaluates its condition, which must be boolean, then only the selected
  branch. let evaluates its initializer, then substitutes it into the body.
  pair evaluates its components left to right; fst / snd project.
- Applying fix f(x). body to v steps to body[f := fix f(x). body][x := v];
  when f == x the parameter shadows f, so only [x := v] is performed.

Target terms contain only Var, Lam, and App, so their evaluation reaches only
the shared cases and never applies a source operation or source substitution.
The machine does not recognize Church encodings.

Budgets count beta-value steps, i.e. applications of a lambda or fix value.
Source let, if, operators, and projections are not counted; every source
divergence goes through function application, so a budget bounds source
runs too. Budget None means unbounded. Execution is restricted to closed
programs: an open program is rejected with OpenTermError before any step.
Source runtime errors (ill-typed operands, unsupported operators, negative
literals) raise SourceError when evaluation reaches them. This module must
not import the compiler.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Final, Literal, cast

from target import Var, Lam, App, Term, is_pure, substitute, term_print
from source_ast import (
    D0E000, d0exp, d0exp_fvset,
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)
from source_visitors import d0exp_pretty, d0exp_substitute

VALUE: Final = "value"
EXHAUSTED: Final = "exhausted"

type Program = Term | d0exp


class OpenTermError(ValueError):
    """Raised when asked to execute a program with free variables."""


class SourceError(RuntimeError):
    """A source-language runtime error, e.g. an ill-typed operand."""


@dataclass(frozen=True)
class Reduction[P: (Var | Lam | App | D0E000)]:
    """Outcome of bounded evaluation; P is the syntax of the program run.

    status is VALUE when term is the resulting value, or EXHAUSTED when
    another beta-value step was needed but the budget was spent; then term
    is the residual (partially evaluated) program. steps counts the
    beta-value steps performed. Exhaustion is not a proof of divergence.
    """
    status: Literal["value", "exhausted"]
    term: P
    steps: int

    @property
    def completed(self) -> bool:
        return self.status == VALUE


########################################################################
# Evaluation-context frames. Each frame records what to do with the value
# of the subexpression under evaluation, and how to rebuild the program
# around a residual term on exhaustion (plug).
########################################################################

@dataclass(frozen=True)
class _Arg:          # [] arg       -- function position under evaluation
    arg: Program
    make: Callable[..., Program]   # App or D0Eapp

    def plug(self, t): return self.make(t, self.arg)


@dataclass(frozen=True)
class _Fun:          # fn []        -- argument under evaluation
    fn: Program
    make: Callable[[Program, Program], Program]

    def plug(self, t): return self.make(self.fn, t)


@dataclass(frozen=True)
class _Op1:          # op []
    name: str

    def plug(self, t): return D0Eop1(self.name, t)


@dataclass(frozen=True)
class _Op2Left:      # [] op right
    name: str
    right: d0exp

    def plug(self, t): return D0Eop2(self.name, t, self.right)


@dataclass(frozen=True)
class _Op2Right:     # left op []
    name: str
    left: d0exp

    def plug(self, t): return D0Eop2(self.name, self.left, t)


@dataclass(frozen=True)
class _ShortLeft:    # [] and/or right
    name: str
    right: d0exp

    def plug(self, t): return D0Eop2(self.name, t, self.right)


@dataclass(frozen=True)
class _ShortRight:   # true and [] / false or []  -- result must be boolean
    name: str

    def plug(self, t): return D0Eop2(self.name, D0Ebtf(self.name == "and"), t)


@dataclass(frozen=True)
class _If:           # if [] then t else f
    then: d0exp
    other: d0exp

    def plug(self, t): return D0Eif0(t, self.then, self.other)


@dataclass(frozen=True)
class _Let:          # let x = [] in body
    name: str
    body: d0exp

    def plug(self, t): return D0Elet(self.name, t, self.body)


@dataclass(frozen=True)
class _PairLeft:     # pair [] right
    right: d0exp

    def plug(self, t): return D0Epair(t, self.right)


@dataclass(frozen=True)
class _PairRight:    # pair left []
    left: d0exp

    def plug(self, t): return D0Epair(self.left, t)


@dataclass(frozen=True)
class _Proj:         # fst [] / snd []
    first: bool

    def plug(self, t): return D0Epfst(t) if self.first else D0Epsnd(t)


type _Frame = (_Arg | _Fun | _Op1 | _Op2Left | _Op2Right | _ShortLeft
               | _ShortRight | _If | _Let | _PairLeft | _PairRight | _Proj)


########################################################################
# Entry points
########################################################################

def evaluate(program: Program, budget: int | None = None,
             trace: list | None = None) -> Reduction[Program]:
    """Evaluate a closed source AST or target term by call-by-value.

    At most budget beta-value steps are performed (None: unbounded). A value
    completes with zero steps, even with budget zero; a value reached on the
    last permitted step counts as completed. If trace is a list, each
    contracted redex is appended to it. The input is not modified.
    """
    if budget is not None and (not isinstance(budget, int)
                               or isinstance(budget, bool) or budget < 0):
        raise ValueError(f"budget must be a nonnegative int or None, got {budget!r}")
    if isinstance(program, (Var, Lam, App)):
        if not is_pure(program):
            raise TypeError("target term contains non-target nodes")
        free = program.fv
    elif isinstance(program, D0E000):
        free = d0exp_fvset(program)
    else:
        raise TypeError(f"not a source AST or target term: {program!r}")
    if free:
        raise OpenTermError(
            f"cannot execute open program; free variables: {sorted(free)}")
    return _run(program, budget, trace)


def reduce_term(term: Term, budget: int,
                trace: list[App] | None = None) -> Reduction[Term]:
    """Evaluate a closed target term with at most budget beta-value steps."""
    if not isinstance(term, (Var, Lam, App)):
        raise TypeError(f"not a target term: {term!r}")
    if budget is None:
        raise ValueError("target reduction requires an explicit budget")
    # Substituting target values into target terms yields target terms.
    return cast(Reduction[Term], evaluate(term, budget, trace))


def evaluate_source(dexp: d0exp, budget: int | None = None) -> Reduction[d0exp]:
    """Evaluate a closed source AST under the source-language rules."""
    if not isinstance(dexp, D0E000):
        raise TypeError(f"not a source AST: {dexp!r}")
    return cast(Reduction[d0exp], evaluate(dexp, budget))


########################################################################
# The machine
########################################################################

def _run(program: Program, budget: int | None, trace: list | None) -> Reduction[Program]:
    stack: list[_Frame] = []
    steps = 0
    current = program
    while True:
        # Descend: find the next subexpression to evaluate, or a value.
        match current:
            case App(fn, arg):
                stack.append(_Arg(arg, App))
                current = fn
                continue
            case D0Eapp(fn, arg):
                stack.append(_Arg(arg, D0Eapp))
                current = fn
                continue
            case Var(x) | D0Evar(x):
                # Unreachable for closed input: substituting closed values
                # keeps every intermediate program closed.
                raise OpenTermError(f"stuck on free variable {x}")
            case Lam() | D0Elam() | D0Efix() | D0Ebtf():
                pass
            case D0Eint(n):
                if n < 0:
                    raise SourceError(f"negative literal {n} is outside the language")
            case D0Epair(left, right):
                if not _is_source_value(current):
                    stack.append(_PairLeft(right))
                    current = left
                    continue
            case D0Eop1(name, arg):
                stack.append(_Op1(name))
                current = arg
                continue
            case D0Eop2("and" | "or" as name, left, right):
                stack.append(_ShortLeft(name, right))
                current = left
                continue
            case D0Eop2(name, left, right):
                stack.append(_Op2Left(name, right))
                current = left
                continue
            case D0Eif0(cond, then, other):
                stack.append(_If(then, other))
                current = cond
                continue
            case D0Elet(name, init, body):
                stack.append(_Let(name, body))
                current = init
                continue
            case D0Epfst(arg) | D0Epsnd(arg):
                stack.append(_Proj(isinstance(current, D0Epfst)))
                current = arg
                continue
            case _:
                raise TypeError(f"unsupported program node: {current!r}")

        # current is a value: return it to the innermost frame.
        value = current
        # Only source frames use src: evaluate() rejects mixed syntax, so a
        # source frame only ever receives a source value.
        src = cast(d0exp, value)
        if not stack:
            return Reduction(VALUE, value, steps)
        frame = stack.pop()
        match frame:
            case _Arg(arg, make):
                stack.append(_Fun(value, make))
                current = arg
            case _Fun(fn):
                if budget is not None and steps == budget:
                    stack.append(frame)
                    return Reduction(EXHAUSTED, _plug(stack, value), steps)
                if trace is not None:
                    trace.append(frame.plug(value))
                steps += 1
                current = _apply(fn, value)
            case _Op1(name):
                current = _op1(name, src)
            case _Op2Left(name, right):
                stack.append(_Op2Right(name, src))
                current = right
            case _Op2Right(name, left):
                current = _op2(name, left, src)
            case _ShortLeft(name, right):
                decided = _expect_bool(src, name).arg1
                if decided == (name == "or"):
                    current = value         # false and _ / true or _
                else:
                    stack.append(_ShortRight(name))
                    current = right
            case _ShortRight(name):
                current = _expect_bool(src, name)
            case _If(then, other):
                current = then if _expect_bool(src, "if").arg1 else other
            case _Let(name, body):
                current = d0exp_substitute(body, name, src)
            case _PairLeft(right):
                stack.append(_PairRight(src))
                current = right
            case _PairRight(left):
                current = D0Epair(left, src)
            case _Proj(first):
                if not isinstance(value, D0Epair):
                    raise SourceError(f"{'fst' if first else 'snd'} expects a pair, "
                                      f"got {_show(value)}")
                current = value.arg1 if first else value.arg2


def _plug(stack: list[_Frame], term: Program) -> Program:
    """Rebuild the whole program from its evaluation context and focus."""
    for frame in reversed(stack):
        term = frame.plug(term)
    return term


def _apply(fn: Program, arg: Program) -> Program:
    """One beta-value step: fn is a function value, arg a value."""
    match fn:
        # evaluate() rejects mixed syntax, so arg has the same syntax as fn.
        case Lam(param, body):
            return substitute(body, param, cast(Term, arg))
        case D0Elam(param, body):
            return d0exp_substitute(body, param, cast(d0exp, arg))
        case D0Efix(fname, param, body):
            if fname != param:
                body = d0exp_substitute(body, fname, fn)
            return d0exp_substitute(body, param, cast(d0exp, arg))
    raise SourceError(f"cannot apply non-function {_show(fn)}")


def _is_source_value(dexp: d0exp) -> bool:
    match dexp:
        case D0Ebtf() | D0Elam() | D0Efix():
            return True
        case D0Eint(n):
            return n >= 0
        case D0Epair(left, right):
            return _is_source_value(left) and _is_source_value(right)
    return False


########################################################################
# Source-language primitive operations (source path only)
########################################################################

_ARITH = {
    "+": lambda m, n: m + n,
    "-": lambda m, n: max(m - n, 0),
    "*": lambda m, n: m * n,
}
_COMPARE = {
    "<": lambda m, n: m < n,
    "<=": lambda m, n: m <= n,
    ">": lambda m, n: m > n,
    ">=": lambda m, n: m >= n,
    "==": lambda m, n: m == n,
    "!=": lambda m, n: m != n,
}


def _op1(name: str, value: d0exp) -> d0exp:
    if name != "not":
        raise SourceError(f"unsupported unary operator {name!r}")
    return D0Ebtf(not _expect_bool(value, name).arg1)


def _op2(name: str, left: d0exp, right: d0exp) -> d0exp:
    if name not in _ARITH and name not in _COMPARE:
        raise SourceError(f"unsupported binary operator {name!r}")
    m, n = _expect_nat(left, name), _expect_nat(right, name)
    if name in _ARITH:
        return D0Eint(_ARITH[name](m, n))
    return D0Ebtf(_COMPARE[name](m, n))


def _expect_bool(value: d0exp, where: str) -> D0Ebtf:
    if not isinstance(value, D0Ebtf):
        raise SourceError(f"{where} expects a boolean, got {_show(value)}")
    return value


def _expect_nat(value: d0exp, where: str) -> int:
    if not isinstance(value, D0Eint):
        raise SourceError(f"{where} expects a natural number, got {_show(value)}")
    return value.arg1


def _show(program: Program) -> str:
    if isinstance(program, (Var, Lam, App)):
        return term_print(program)
    return d0exp_pretty(program)


########################################################################
# Results
########################################################################

def source_result(value: d0exp) -> int | bool | tuple | d0exp:
    """Convert a source value to Python data: naturals to int, booleans to
    bool, pairs to tuples; functions are returned unchanged."""
    match value:
        case D0Ebtf(b):
            return b
        case D0Eint(n):
            return n
        case D0Epair(left, right):
            return (source_result(left), source_result(right))
    return value


def describe(result: Reduction) -> str:
    """One-line human-readable summary of an evaluation outcome."""
    if result.completed:
        return f"value after {result.steps} steps: {_show(result.term)}"
    return f"budget exhausted after {result.steps} steps"
