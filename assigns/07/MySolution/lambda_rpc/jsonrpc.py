"""JSON-RPC 2.0 envelope handling, independent of any web framework.

This module knows nothing about HTTP or LAMBDA3. It turns a raw request body
(bytes) into a JSON-RPC reply (a dict, a list, or None for "no response"),
calling methods from a registry that maps method names to callables taking a
``params`` value and returning a JSON-serializable result.

See RPC.md section 2 for the contract implemented here.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from typing import Any

log = logging.getLogger(__name__)

# Standard JSON-RPC 2.0 error codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

MAX_BATCH_SIZE = 25

_ALLOWED_MEMBERS = frozenset({"jsonrpc", "method", "params", "id"})

type Json = Any
type Method = Callable[[Json], Json]


class RpcError(Exception):
    """An error that becomes a JSON-RPC ``error`` object.

    ``message`` must be a fixed, client-safe string; ``data`` an optional dict
    of client-safe details. Never put exception text from unknown sources here.
    """

    def __init__(self, code: int, message: str, data: dict[str, Json] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def to_json(self) -> dict[str, Json]:
        error: dict[str, Json] = {"code": self.code, "message": self.message}
        if self.data is not None:
            error["data"] = self.data
        return error


def invalid_request(reason: str, **extra: Json) -> RpcError:
    return RpcError(INVALID_REQUEST, "Invalid Request", {"reason": reason, **extra})


def invalid_params(param: str, reason: str, **extra: Json) -> RpcError:
    return RpcError(INVALID_PARAMS, "Invalid params", {"param": param, "reason": reason, **extra})


def success_response(request_id: Json, result: Json) -> dict[str, Json]:
    return {"jsonrpc": "2.0", "result": result, "id": request_id}


def error_response(request_id: Json, error: RpcError) -> dict[str, Json]:
    return {"jsonrpc": "2.0", "error": error.to_json(), "id": request_id}


def _reject_constant(name: str) -> None:
    # Python's json accepts NaN/Infinity, which are not JSON.
    raise ValueError(f"non-standard JSON constant {name}")


def _is_valid_id(value: Json) -> bool:
    # bool is a subclass of int in Python but is not a valid JSON-RPC id.
    return value is None or isinstance(value, str) or (
        isinstance(value, (int, float)) and not isinstance(value, bool)
    )


class Dispatcher:
    """Validate JSON-RPC envelopes and dispatch them to registered methods."""

    def __init__(self, methods: Mapping[str, Method]):
        self._methods = dict(methods)

    # -- entry point ---------------------------------------------------------

    def handle_body(self, body: bytes) -> Json | None:
        """Return the reply for an HTTP body, or None when nothing is sent back."""
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            return error_response(None, RpcError(PARSE_ERROR, "Parse error", {"reason": "invalid_utf8"}))
        try:
            payload = json.loads(text, parse_constant=_reject_constant)
        except ValueError:
            return error_response(None, RpcError(PARSE_ERROR, "Parse error", {"reason": "invalid_json"}))
        return self.handle_payload(payload)

    def handle_payload(self, payload: Json) -> Json | None:
        if isinstance(payload, list):
            return self._handle_batch(payload)
        return self._handle_single(payload)

    # -- batches -------------------------------------------------------------

    def _handle_batch(self, items: list[Json]) -> Json | None:
        if not items:
            return error_response(None, invalid_request("empty_batch"))
        if len(items) > MAX_BATCH_SIZE:
            return error_response(None, invalid_request("batch_too_large", limit=MAX_BATCH_SIZE))
        responses = [r for r in map(self._handle_single, items) if r is not None]
        return responses or None

    # -- single requests -----------------------------------------------------

    def _handle_single(self, request: Json) -> dict[str, Json] | None:
        try:
            method, params, has_id, request_id = self._validate_envelope(request)
        except RpcError as error:
            # An invalid request cannot be a valid notification: always answer,
            # with id null (RPC.md section 2.2).
            return error_response(None, error)

        try:
            result = self._call(method, params)
        except RpcError as error:
            return error_response(request_id, error) if has_id else None
        except Exception:
            log.exception("Unexpected failure in method %r", method)
            internal = RpcError(INTERNAL_ERROR, "Internal error")
            return error_response(request_id, internal) if has_id else None

        return success_response(request_id, result) if has_id else None

    @staticmethod
    def _validate_envelope(request: Json) -> tuple[str, Json, bool, Json]:
        if not isinstance(request, dict):
            raise invalid_request("not_an_object")
        for member in request:
            if member not in _ALLOWED_MEMBERS:
                raise invalid_request("unexpected_member", member=member)
        if request.get("jsonrpc") != "2.0":
            raise invalid_request("bad_jsonrpc")
        method = request.get("method")
        if not isinstance(method, str):
            raise invalid_request("bad_method")
        has_id = "id" in request
        request_id = request.get("id")
        if has_id and not _is_valid_id(request_id):
            raise invalid_request("bad_id")
        params = request.get("params")
        if "params" in request and not isinstance(params, (dict, list)):
            raise invalid_request("bad_params")
        return method, params, has_id, request_id

    def _call(self, method: str, params: Json) -> Json:
        handler = self._methods.get(method)
        if handler is None:
            raise RpcError(METHOD_NOT_FOUND, "Method not found", {"method": method})
        return handler(params)
