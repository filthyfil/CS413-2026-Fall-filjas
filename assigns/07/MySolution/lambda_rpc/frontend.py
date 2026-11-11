"""Thin wrapper that loads LAMBDA3 and runs its parser and type checker.

Shared by the server process and the interpretation worker process, so both
build the program in exactly the same way. Nothing here re-implements LAMBDA3:
it only locates the module, loads the ``mylib`` libraries, and labels a stack
overflow with the stage where it happened.
"""

from __future__ import annotations

import os
import sys
import traceback
from functools import cache
from pathlib import Path
from typing import Any

LAMBDA3_DIR = Path(
    os.environ.get("LAMBDA3_DIR", Path(__file__).resolve().parents[2] / "LAMBDA3")
)
if str(LAMBDA3_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA3_DIR))

import lambda3 as L  # noqa: E402  (path set up above)
from basics0 import fnlist, fnlist_cons, fnlist_nil, fnlist_reverse  # noqa: E402

__all__ = ["L", "LIBRARIES", "STACK_DETAIL", "StackLimitExceeded", "parse_and_typecheck"]

LIBRARIES: tuple[str, ...] = ("list", "optn", "a1sz", "strm")

STACK_DETAIL = "Python call stack exhausted"


class StackLimitExceeded(Exception):
    """LAMBDA3 hit Python's recursion limit while processing a program."""

    def __init__(self, stage: str):
        super().__init__(stage)
        self.stage = stage


@cache
def _library_declarations(name: str) -> tuple[Any, ...]:
    """Parse one mylib module into a tuple of declarations (cached)."""
    source = (LAMBDA3_DIR / "mylib" / f"{name}.lam").read_text()
    items: list[Any] = []
    decls = L.d0cls_parse(source)
    while isinstance(decls, fnlist_cons):
        items.append(decls.arg1)
        decls = decls.arg2
    return tuple(items)


def _as_fnlist(items: list[Any]) -> fnlist[Any]:
    result: fnlist[Any] = fnlist_nil()
    for item in items:
        result = fnlist_cons(item, result)
    return fnlist_reverse(result)


def _overflow_stage(error: RecursionError) -> str:
    """Report 'typecheck' if the overflow happened inside the type checker."""
    for frame, _ in traceback.walk_tb(error.__traceback__):
        if frame.f_code.co_name == "d0exp_typecheck":
            return "typecheck"
    return "parse"


def parse_and_typecheck(source: str, libraries: tuple[str, ...] = ()) -> tuple[Any, Any]:
    """Return ``(expression, type)`` for a source program.

    Without libraries this is exactly ``L.d0exp_parse_and_typecheck``. With
    libraries, the selected mylib declarations wrap the parsed expression in a
    ``D0Elets`` and the whole program is type-checked.

    Raises ``L.LambdaSyntaxError``, ``L.TypeCheckError``, or
    ``StackLimitExceeded``.
    """
    try:
        if not libraries:
            expression, typ = L.d0exp_parse_and_typecheck(source)
            return expression, typ
        expression = L.d0exp_parse(source)
        declarations = [d for name in libraries for d in _library_declarations(name)]
        program = L.D0Elets(_as_fnlist(declarations), expression)
        return program, L.d0exp_typecheck(program)
    except RecursionError as error:
        raise StackLimitExceeded(_overflow_stage(error)) from None
