"""Language-tool adapter: the only web code that talks to the A06 core.

Adapted from assigns/04/MySolution/server/tools.py. Every operation returns
a result dict:

    {"op": str, "revision": int, "status": STATUS, "message": str,
     "errorKind": ERROR_KIND | None, "value": str | None, "details": dict}

STATUS is "ok", "error" (problem with the user's program), "failure" (the
tools themselves broke), "not_implemented" or "cancelled". ERROR_KIND is
"input", "language", "runtime" or "backend".

    Lint       static checks only: free variables and compiler support
    Interpret  the shared evaluator's source path (unbounded; Stop works)
    Compile    compile_expr; the artifact carries the printed pure term
    Execute    bounded reduction, then bounded observation as the chosen kind
"""
from . import _CORE  # noqa: F401  (sets up the import path)
from .reader import ReadError, read_d0exp
from .runner import InterpretRunner

from compiler import CompileError, compile_expr
from evaluator import OpenTermError, SourceError, source_result
from evaluator import evaluate_source as evaluate_source_ast
from observe import EXHAUSTED as OBS_EXHAUSTED
from pipeline import (
    DEFAULT_EXEC_BUDGET, DEFAULT_OBS_BUDGET, format_kind, format_value,
    parse_kind, run_compiled,
)
from source_ast import D0Elam, D0Efix, d0exp_fvset
from source_visitors import d0exp_pretty
from target import free_vars, is_pure, term_print
from term_parser import TermParseError, term_parse

ARTIFACT_FORMAT = "pure-lambda"
MAX_BUDGET = 5_000_000


def make_result(op: str, revision: int | None, status: str, message: str, *,
                error_kind: str | None = None, value: str | None = None,
                details: dict | None = None) -> dict:
    return {"op": op, "revision": revision, "status": status,
            "message": message, "errorKind": error_kind, "value": value,
            "details": details or {}}


def lint_source(source: str) -> tuple[str, str, str | None, dict]:
    """(status, message, error_kind, details) for Lint. Never evaluates."""
    try:
        dexp = read_d0exp(source)
    except ReadError as exc:
        return "error", f"Invalid input: {exc}", "input", {}
    names = sorted(d0exp_fvset(dexp))
    if names:
        return ("error", "Undeclared variable(s): " + ", ".join(names),
                "language", {"freeVariables": names})
    try:
        compile_expr(dexp)
    except CompileError as exc:
        return "error", f"Not in the source language: {exc}", "language", {}
    return ("ok", "No free variables; every literal and operator is supported.",
            None, {"freeVariables": []})


def show_source_value(value) -> str:
    if isinstance(value, (D0Elam, D0Efix)):
        return f"function {d0exp_pretty(value)}"
    return format_value(value)


def evaluate_source(source: str) -> tuple[str, str, str | None, str | None]:
    """(status, message, error_kind, value) for Interpret.

    Runs the shared evaluator's source path in the calling process;
    InterpretRunner calls this inside a child process so a run can be stopped.
    """
    try:
        dexp = read_d0exp(source)
    except ReadError as exc:
        return "error", f"Invalid input: {exc}", "input", None
    try:
        result = evaluate_source_ast(dexp)
    except OpenTermError as exc:
        return "error", f"Runtime error: {exc}", "language", None
    except SourceError as exc:
        return "error", f"Runtime error: {exc}", "runtime", None
    except RecursionError:
        return ("error", "Runtime error: term nested too deeply (RecursionError)",
                "runtime", None)
    value = source_result(result.term)
    if isinstance(value, tuple):
        text = format_value(value)
    else:
        text = show_source_value(value)
    return ("ok", f"Evaluation succeeded after {result.steps} function "
            f"applications.", None, text)


class LanguageTools:
    """Backend entry points used by the HTTP layer (server/app.py)."""

    def __init__(self, runner: InterpretRunner | None = None):
        self.runner = runner or InterpretRunner()

    def lint(self, source: str, revision: int) -> dict:
        status, message, kind, details = lint_source(source)
        return make_result("lint", revision, status, message,
                           error_kind=kind, details=details)

    def interpret(self, source: str, revision: int, run_id: str) -> dict:
        outcome = self.runner.run(source, run_id)
        if outcome.cancelled:
            return make_result("interpret", revision, "cancelled",
                               "Interpretation was stopped by the user.")
        if outcome.crash is not None:
            return make_result("interpret", revision, "failure",
                               f"Interpreter process failed: {outcome.crash}",
                               error_kind="backend")
        if outcome.result is None:
            return make_result("interpret", revision, "failure",
                               "Interpreter process returned no result.",
                               error_kind="backend")
        status, message, kind, value = outcome.result
        return make_result("interpret", revision, status, message,
                           error_kind=kind, value=value)

    def cancel(self, run_id: str) -> bool:
        return self.runner.cancel(run_id)

    def typecheck(self, source: str, revision: int) -> dict:
        return make_result("typecheck", revision, "not_implemented",
                           "Type checking is not part of this project.")

    def compile(self, source: str, revision: int) -> dict:
        try:
            dexp = read_d0exp(source)
        except ReadError as exc:
            return make_result("compile", revision, "error",
                               f"Invalid input: {exc}", error_kind="input")
        try:
            term = compile_expr(dexp)
        except CompileError as exc:
            return make_result("compile", revision, "error",
                               f"Compilation error: {exc}", error_kind="language")
        except RecursionError:
            return make_result("compile", revision, "error",
                               "Compilation error: program nested too deeply",
                               error_kind="input")
        code = term_print(term)
        message = (f"Compiled to a pure lambda term of {len(code)} characters "
                   f"(only variables, lam, and application).")
        free = sorted(free_vars(term))
        if free:
            message += (" The program is open (free: " + ", ".join(free) +
                        "), so Execute will reject it.")
        artifact = {"revision": revision, "format": ARTIFACT_FORMAT, "code": code}
        return make_result("compile", revision, "ok", message, value=code,
                           details={"artifact": artifact, "freeVariables": free})

    def execute(self, artifact: dict | None, revision: int,
                kind: str = "nat", exec_budget: int = DEFAULT_EXEC_BUDGET,
                obs_budget: int = DEFAULT_OBS_BUDGET) -> dict:
        def error(message: str, error_kind: str = "input", **extra) -> dict:
            return make_result("execute", revision, "error", message,
                               error_kind=error_kind, **extra)

        if not artifact:
            return error("Execute runs code generated by Compile. "
                         "Compile this revision first.")
        if artifact.get("revision") != revision:
            return error("The artifact belongs to a different source revision; "
                         "compile again.")
        if artifact.get("format") != ARTIFACT_FORMAT or not isinstance(artifact.get("code"), str):
            return error("The artifact is not a pure lambda term; compile again.")
        for label, budget in (("Execution", exec_budget), ("Observation", obs_budget)):
            if not 0 <= budget <= MAX_BUDGET:
                return error(f"{label} budget must be between 0 and {MAX_BUDGET}.")
        try:
            expected = parse_kind(kind)
        except ValueError as exc:
            return error(f"Result kind: {exc}")
        try:
            term = term_parse(artifact["code"])
        except (TermParseError, RecursionError) as exc:
            return error(f"The artifact could not be read: {exc}")
        if not is_pure(term):
            return error("The artifact is not a pure lambda term.")
        try:
            result = run_compiled(term, expected, exec_budget, obs_budget)
        except OpenTermError as exc:
            return error(f"Cannot execute an open program: {exc}", "language")
        except RecursionError:
            return error("Execution failed: term nested too deeply (RecursionError)",
                         "runtime")

        ex, obs = result.execution, result.observation
        details = {"execStatus": ex.status, "execSteps": ex.steps,
                   "execBudget": exec_budget, "obsBudget": obs_budget,
                   "kind": format_kind(expected)}
        lines = []
        if ex.completed:
            lines.append(f"Execution: value after {ex.steps} beta-value steps "
                         f"(budget {exec_budget}).")
        else:
            lines.append(f"Execution: budget exhausted after {ex.steps} beta-value "
                         f"steps (budget {exec_budget}). This is not a proof of "
                         f"nontermination.")
            return error("\n".join(lines), "runtime", details=details)
        assert obs is not None          # observation runs whenever execution completes
        details |= {"obsStatus": obs.status, "obsSteps": obs.steps}
        if obs.decoded:
            lines.append(f"Observation: decoded as {format_kind(expected)} after "
                         f"{obs.steps} beta-value steps (budget {obs_budget}).")
            return make_result("execute", revision, "ok", "\n".join(lines),
                               value=format_value(obs.value), details=details)
        if obs.status == OBS_EXHAUSTED:
            lines.append(f"Observation: budget exhausted after {obs.steps} "
                         f"beta-value steps (budget {obs_budget}).")
        else:
            lines.append(f"Observation: the value is not a valid "
                         f"{format_kind(expected)} encoding ({obs.detail}). "
                         f"Check the result kind.")
        return error("\n".join(lines), "runtime", details=details)

    def shutdown(self) -> None:
        self.runner.shutdown()
