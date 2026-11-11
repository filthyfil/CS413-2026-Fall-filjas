"""Service layer: the four RPC methods, wrapping LAMBDA3.

Each method takes the raw JSON ``params`` value, validates it, calls LAMBDA3
through :mod:`frontend` / :mod:`worker`, and returns a JSON result or raises
an :class:`RpcError`. This module knows nothing about HTTP or envelopes.

See RPC.md sections 3-5.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from . import API_VERSION, frontend, worker
from .jsonrpc import Json, Method, RpcError, invalid_params

# Application error codes (RPC.md section 4.1).
LAMBDA_SYNTAX_ERROR = -32010
LAMBDA_TYPE_ERROR = -32011
EXECUTION_TIMEOUT = -32012
LAMBDA_RUNTIME_ERROR = -32013
STACK_LIMIT_EXCEEDED = -32014

MAX_SOURCE_BYTES = 65_536
DEFAULT_TIMEOUT_SECONDS = 5.0
TARGETS = ("python", "javascript")


def default_timeout() -> float:
    return float(os.environ.get("LAMBDA_RPC_TIMEOUT", DEFAULT_TIMEOUT_SECONDS))


# -- error constructors ---------------------------------------------------------

def syntax_error(detail: str, line: int | None, column: int | None, text: str | None) -> RpcError:
    return RpcError(LAMBDA_SYNTAX_ERROR, "LAMBDA syntax error",
                    {"detail": detail, "line": line, "column": column, "text": text})


def type_error(detail: str) -> RpcError:
    return RpcError(LAMBDA_TYPE_ERROR, "LAMBDA type error", {"detail": detail})


def runtime_error(detail: str) -> RpcError:
    return RpcError(LAMBDA_RUNTIME_ERROR, "LAMBDA runtime error", {"detail": detail})


def stack_limit(stage: str) -> RpcError:
    return RpcError(STACK_LIMIT_EXCEEDED, "Stack limit exceeded",
                    {"stage": stage, "detail": frontend.STACK_DETAIL})


def timeout_error(seconds: float) -> RpcError:
    return RpcError(EXECUTION_TIMEOUT, "Execution timeout", {"timeoutSeconds": seconds})


# -- parameter validation -------------------------------------------------------

type Result = dict[str, Any]
type Interpreter = Callable[[str, tuple[str, ...], float], worker.Outcome]


def _require_object(params: Json, allowed: set[str]) -> dict[str, Json]:
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise invalid_params("params", "not_an_object")
    for name in params:
        if name not in allowed:
            raise invalid_params(name, "unexpected_param")
    return params


def _source_param(params: dict[str, Json]) -> str:
    if "source" not in params:
        raise invalid_params("source", "missing")
    source = params["source"]
    if not isinstance(source, str):
        raise invalid_params("source", "wrong_type")
    if not source.strip():
        raise invalid_params("source", "blank")
    size = len(source.encode("utf-8", errors="surrogatepass"))
    if size > MAX_SOURCE_BYTES:
        raise invalid_params("source", "too_large", limitBytes=MAX_SOURCE_BYTES, actualBytes=size)
    return source


def _libraries_param(params: dict[str, Json]) -> tuple[str, ...]:
    libraries = params.get("libraries", [])
    if not isinstance(libraries, list) or not all(isinstance(n, str) for n in libraries):
        raise invalid_params("libraries", "wrong_type")
    for name in libraries:
        if name not in frontend.LIBRARIES:
            raise invalid_params("libraries", "unknown_library", allowed=list(frontend.LIBRARIES))
    if len(set(libraries)) != len(libraries):
        raise invalid_params("libraries", "duplicate_library")
    return tuple(libraries)


def _target_param(params: dict[str, Json]) -> str:
    if "target" not in params:
        raise invalid_params("target", "missing")
    target = params["target"]
    if not isinstance(target, str):
        raise invalid_params("target", "wrong_type")
    if target not in TARGETS:
        raise invalid_params("target", "unsupported_target", allowed=list(TARGETS))
    return target


# -- the service ----------------------------------------------------------------

class LambdaService:
    """The RPC methods. ``interpreter`` is injectable for failure tests."""

    def __init__(self, timeout: float | None = None, interpreter: Interpreter = worker.interpret):
        self.timeout = default_timeout() if timeout is None else timeout
        self.interpreter = interpreter

    def methods(self) -> dict[str, Method]:
        return {
            "service.health": self.health,
            "lambda.typecheck": self.typecheck,
            "lambda.interpret": self.interpret,
            "lambda.compile": self.compile,
        }

    # Parse and type-check in the server: syntax and type errors are reported
    # without starting a worker, and nothing runs unless both succeed.
    @staticmethod
    def _check(source: str, libraries: tuple[str, ...]) -> tuple[Any, Any]:
        L = frontend.L
        try:
            return frontend.parse_and_typecheck(source, libraries)
        except L.LambdaSyntaxError as error:
            raise syntax_error(error.msg, error.lineno, error.offset, error.text) from None
        except L.TypeCheckError as error:
            raise type_error(str(error)) from None
        except frontend.StackLimitExceeded as error:
            raise stack_limit(error.stage) from None

    def health(self, params: Json) -> Result:
        _require_object(params, set())
        return {"status": "ok", "version": API_VERSION}

    def typecheck(self, params: Json) -> Result:
        params = _require_object(params, {"source", "libraries"})
        source, libraries = _source_param(params), _libraries_param(params)
        _, typ = self._check(source, libraries)
        return {"type": frontend.L.format_type(typ)}

    def interpret(self, params: Json) -> Result:
        params = _require_object(params, {"source", "libraries"})
        source, libraries = _source_param(params), _libraries_param(params)
        self._check(source, libraries)
        match self.interpreter(source, libraries, self.timeout):
            case worker.Ok(type=typ, value=value):
                return {"type": typ, "value": value}
            case worker.Timeout():
                raise timeout_error(self.timeout)
            case worker.RuntimeFailure(detail=detail):
                raise runtime_error(detail)
            case worker.StackFailure(stage=stage):
                raise stack_limit(stage)
            # The server already checked the program, so these are unexpected,
            # but map them faithfully rather than hiding them.
            case worker.SyntaxFailure(detail=detail, line=line, column=column, text=text):
                raise syntax_error(detail, line, column, text)
            case worker.TypeFailure(detail=detail):
                raise type_error(detail)
            case worker.InternalFailure():
                raise RuntimeError("interpretation worker failed")

    def compile(self, params: Json) -> Result:
        params = _require_object(params, {"source", "target", "libraries"})
        source, libraries = _source_param(params), _libraries_param(params)
        target = _target_param(params)
        expression, _ = self._check(source, libraries)
        L = frontend.L
        compiler = L.d0exp_compile if target == "python" else L.d0exp_compile_js
        try:
            code = compiler(expression)
        except RecursionError:
            raise stack_limit("compile") from None
        return {"target": target, "code": code}
