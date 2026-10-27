"""End-to-end pipeline: compile, execute with a budget, observe with a budget.

Used by the command-line demonstration (demo.py) and the web front-end
(web/server/tools.py). Execution and observation have separate budgets and
separate beta-value step counts:

    execution    reduce_term(C[e], exec_budget)       -> a lambda value
    observation  observe(value, kind, obs_budget)     -> decoded data

Observation runs only if execution completed. Neither phase performs the
encoded arithmetic in Python.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from compiler import compile_expr
from evaluator import Reduction, reduce_term
from observe import Kind, Observation, observe
from source_ast import d0exp
from target import Term

DEFAULT_EXEC_BUDGET = 100_000
DEFAULT_OBS_BUDGET = 100_000


@dataclass(frozen=True)
class PipelineResult:
    term: Term
    execution: Reduction
    observation: Observation | None     # None when execution was exhausted

    @property
    def decoded(self) -> bool:
        return self.observation is not None and self.observation.decoded

    @property
    def value(self):
        return self.observation.value if self.decoded else None


def run_compiled(term: Term, kind: Kind, exec_budget: int = DEFAULT_EXEC_BUDGET,
                 obs_budget: int = DEFAULT_OBS_BUDGET) -> PipelineResult:
    """Execute a compiled closed term, then observe it as kind."""
    execution = reduce_term(term, exec_budget)
    if not execution.completed:
        return PipelineResult(term, execution, None)
    return PipelineResult(term, execution, observe(execution.term, kind, obs_budget))


def run_pipeline(dexp: d0exp, kind: Kind, exec_budget: int = DEFAULT_EXEC_BUDGET,
                 obs_budget: int = DEFAULT_OBS_BUDGET) -> PipelineResult:
    """Compile a closed source AST, execute it, and observe the result."""
    return run_compiled(compile_expr(dexp), kind, exec_budget, obs_budget)


########################################################################
# Result kinds as text: nat | bool | (kind, kind)
########################################################################

_KIND_TOKEN = re.compile(r"\s*(nat|bool|[(),])")


def parse_kind(text: str) -> Kind:
    """Parse "nat", "bool", or a pair such as "(nat, (bool, nat))"."""
    tokens, pos = [], 0
    text = text.strip()
    while pos < len(text):
        m = _KIND_TOKEN.match(text, pos)
        if m is None:
            raise ValueError(f"invalid result kind {text!r}: use nat, bool, or (kind, kind)")
        tokens.append(m.group(1))
        pos = m.end()

    def kind(i: int) -> tuple[Kind, int]:
        if i >= len(tokens):
            raise ValueError(f"incomplete result kind {text!r}")
        if tokens[i] == "nat":
            return "nat", i + 1
        if tokens[i] == "bool":
            return "bool", i + 1
        if tokens[i] != "(":
            raise ValueError(f"invalid result kind {text!r}")
        left, i = kind(i + 1)
        if i >= len(tokens) or tokens[i] != ",":
            raise ValueError(f"expected ',' in result kind {text!r}")
        right, i = kind(i + 1)
        if i >= len(tokens) or tokens[i] != ")":
            raise ValueError(f"expected ')' in result kind {text!r}")
        return (left, right), i + 1

    result, end = kind(0)
    if end != len(tokens):
        raise ValueError(f"unexpected text after result kind {text!r}")
    return result


def format_kind(kind: Kind) -> str:
    if isinstance(kind, tuple):
        return f"({format_kind(kind[0])}, {format_kind(kind[1])})"
    return kind


def format_value(value) -> str:
    """Show decoded data in source notation: 14, true, (2, true)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, tuple):
        return "(" + ", ".join(format_value(v) for v in value) + ")"
    return str(value)
