"""Run LAMBDA3 interpretation in a separate process with a hard deadline.

The LAMBDA3 interpreter is recursive and has no step budget, so a running
evaluation cannot be interrupted inside the server. Each call gets a fresh
child process. If the deadline passes, the child is terminated.

The child receives the *source text* (a plain string), not a parsed
expression, and sends back one of the small ``Outcome`` dataclasses below,
which hold only strings and ints. Nothing LAMBDA3-specific (closures,
environments) is ever pickled.
"""

from __future__ import annotations

import multiprocessing
import os
import sys
import traceback
from dataclasses import dataclass
from multiprocessing.connection import Connection
from multiprocessing.context import ForkServerContext, SpawnContext

from . import frontend


# -- outcomes reported by the worker ------------------------------------------

@dataclass(frozen=True)
class Ok:
    type: str
    value: str


@dataclass(frozen=True)
class SyntaxFailure:
    detail: str
    line: int | None
    column: int | None
    text: str | None


@dataclass(frozen=True)
class TypeFailure:
    detail: str


@dataclass(frozen=True)
class RuntimeFailure:
    detail: str


@dataclass(frozen=True)
class StackFailure:
    stage: str


@dataclass(frozen=True)
class InternalFailure:
    """The child crashed or hit an unexpected error (logged on its stderr)."""


@dataclass(frozen=True)
class Timeout:
    """Set by the parent when the deadline passes; never sent by the child."""


type Outcome = Ok | SyntaxFailure | TypeFailure | RuntimeFailure | StackFailure | InternalFailure | Timeout


# -- process context -------------------------------------------------------------

def _make_context() -> ForkServerContext | SpawnContext:
    # forkserver: children fork from a small single-threaded server process that
    # has already imported LAMBDA3, which is fast and safe with a threaded web
    # server. Fall back to spawn where forkserver is not available.
    if "forkserver" in multiprocessing.get_all_start_methods():
        context = multiprocessing.get_context("forkserver")
        context.set_forkserver_preload([__name__])
        return context
    return multiprocessing.get_context("spawn")


_CONTEXT = _make_context()


# -- the child -------------------------------------------------------------------

def _evaluate(source: str, libraries: tuple[str, ...]) -> Outcome:
    L = frontend.L
    try:
        expression, typ = frontend.parse_and_typecheck(source, libraries)
    except frontend.StackLimitExceeded as error:
        return StackFailure(error.stage)
    except L.LambdaSyntaxError as error:
        return SyntaxFailure(error.msg, error.lineno, error.offset, error.text)
    except L.TypeCheckError as error:
        return TypeFailure(str(error))

    # Exceptions LAMBDA3's evaluator raises for well-typed programs that fail
    # at run time carry LAMBDA-level messages (for example
    # "list_head: nonempty list expected"). A TypeError from the evaluator
    # would mean the checker and interpreter disagree; it is left to the
    # caller's catch-all and reported as internal.
    try:
        value = L.d0val_format(L.d0exp_evaluate(expression))
    except RecursionError:
        return StackFailure("evaluate")
    except ZeroDivisionError:
        return RuntimeFailure("division by zero")
    except (ValueError, IndexError) as error:
        return RuntimeFailure(str(error))
    return Ok(L.format_type(typ), value)


def _child_main(source: str, libraries: tuple[str, ...], conn: Connection) -> None:
    """Entry point of the worker process."""
    # LAMBDA's print writes to stdout; that output is not part of the result.
    sys.stdout = open(os.devnull, "w")
    outcome: Outcome
    try:
        outcome = _evaluate(source, libraries)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        outcome = InternalFailure()
    conn.send(outcome)
    conn.close()


# -- the parent ------------------------------------------------------------------

def interpret(source: str, libraries: tuple[str, ...], timeout: float) -> Outcome:
    """Interpret ``source`` in a child process, waiting at most ``timeout`` seconds."""
    receiver, sender = _CONTEXT.Pipe(duplex=False)
    process = _CONTEXT.Process(target=_child_main, args=(source, libraries, sender), daemon=True)
    process.start()
    sender.close()
    try:
        if not receiver.poll(timeout):
            return Timeout()
        try:
            outcome: Outcome = receiver.recv()
        except EOFError:
            # Child died without reporting (crash, killed by the OS, ...).
            return InternalFailure()
        return outcome
    finally:
        receiver.close()
        if process.is_alive():
            process.terminate()
            process.join(1)
            if process.is_alive():
                process.kill()
        process.join()
