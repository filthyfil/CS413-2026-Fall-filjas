"""Service layer: the four RPC methods over the LAMBDA3 queens solver.

Each method takes the raw JSON ``params`` value, validates it completely,
then calls the solver/stream table and returns a JSON result or raises an
:class:`RpcError`. This module knows nothing about HTTP or envelopes.
Following Assign07, the method registry is a fixed dict, so a request can
never name an arbitrary function.

See DESIGN.md ("RPC methods" and "Errors").
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

from . import API_VERSION
from .jsonrpc import Json, Method, RpcError, invalid_params
from .solver import QueensSolver
from .streams import DEFAULT_MAX_STREAMS, DEFAULT_TTL_SECONDS, StreamNotFound, StreamTable, TableFull

# Application error codes (DESIGN.md, "Errors").
STREAM_NOT_FOUND = -32001
TOO_MANY_STREAMS = -32002

MIN_SIZE, MAX_SIZE = 4, 10
MIN_LIMIT, MAX_LIMIT = 1, 32
DEFAULT_LIMIT = 1
MAX_STREAM_ID_LENGTH = 64

type Result = dict[str, Any]


def default_ttl() -> float:
    return float(os.environ.get("QUEENS_STREAM_TTL", DEFAULT_TTL_SECONDS))


# -- error constructors ---------------------------------------------------------

def stream_not_found(stream_id: str) -> RpcError:
    return RpcError(STREAM_NOT_FOUND, "Unknown stream",
                    {"stream_id": stream_id, "reason": "unknown_closed_or_expired"})


def too_many_streams(limit: int) -> RpcError:
    return RpcError(TOO_MANY_STREAMS, "Too many open streams", {"limit": limit})


# -- parameter validation -------------------------------------------------------

def _require_object(params: Json, allowed: set[str]) -> dict[str, Json]:
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise invalid_params("params", "not_an_object")
    for name in params:
        if name not in allowed:
            raise invalid_params(name, "unexpected_param")
    return params


def _int_param(params: dict[str, Json], name: str, low: int, high: int,
               default: int | None = None) -> int:
    if name not in params:
        if default is None:
            raise invalid_params(name, "missing")
        return default
    value = params[name]
    # bool is a subclass of int; 8.0 is a float. Neither is accepted.
    if isinstance(value, bool) or not isinstance(value, int):
        raise invalid_params(name, "wrong_type")
    if not low <= value <= high:
        raise invalid_params(name, "out_of_range", min=low, max=high)
    return value


def _stream_id_param(params: dict[str, Json]) -> str:
    if "stream_id" not in params:
        raise invalid_params("stream_id", "missing")
    stream_id = params["stream_id"]
    if not isinstance(stream_id, str):
        raise invalid_params("stream_id", "wrong_type")
    if not stream_id or len(stream_id) > MAX_STREAM_ID_LENGTH:
        raise invalid_params("stream_id", "bad_length", maxLength=MAX_STREAM_ID_LENGTH)
    return stream_id


# -- the service ----------------------------------------------------------------

class QueensService:
    """The RPC methods. ``solver``, ``clock`` and the table limits are
    injectable so tests can count forcing and expire streams without sleeping."""

    def __init__(self, solver: QueensSolver | None = None, *,
                 ttl_seconds: float | None = None,
                 max_streams: int = DEFAULT_MAX_STREAMS,
                 clock: Callable[[], float] = time.monotonic):
        self.solver = solver or QueensSolver()
        self.streams = StreamTable(default_ttl() if ttl_seconds is None else ttl_seconds,
                                   max_streams, clock)

    def methods(self) -> dict[str, Method]:
        return {
            "service.health": self.health,
            "queens.open": self.open,
            "queens.next": self.next,
            "queens.close": self.close,
        }

    def health(self, params: Json) -> Result:
        _require_object(params, set())
        return {"status": "ok", "version": API_VERSION}

    def open(self, params: Json) -> Result:
        params = _require_object(params, {"size"})
        size = _int_param(params, "size", MIN_SIZE, MAX_SIZE)
        # All input is valid before anything is allocated. open() does no search.
        stream = self.solver.open(size)
        try:
            stream_id = self.streams.add(stream)
        except TableFull:
            raise too_many_streams(self.streams.max_streams) from None
        return {"stream_id": stream_id, "size": size}

    def next(self, params: Json) -> Result:
        params = _require_object(params, {"stream_id", "limit"})
        stream_id = _stream_id_param(params)
        limit = _int_param(params, "limit", MIN_LIMIT, MAX_LIMIT, DEFAULT_LIMIT)
        try:
            events, done = self.streams.take(stream_id, limit)
        except StreamNotFound:
            raise stream_not_found(stream_id) from None
        return {"events": events, "done": done}

    def close(self, params: Json) -> Result:
        params = _require_object(params, {"stream_id"})
        stream_id = _stream_id_param(params)
        try:
            self.streams.close(stream_id)
        except StreamNotFound:
            raise stream_not_found(stream_id) from None
        return {"closed": True}
