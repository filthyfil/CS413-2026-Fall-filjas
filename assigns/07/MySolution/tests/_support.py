"""Shared helpers for the in-process HTTP tests.

Every response that goes through these helpers is checked at both layers:

* HTTP transport: status code and Content-Type.
* JSON-RPC: the body is validated against ``rpc.schema.json``, so it has
  exactly one of ``result``/``error``, a well-formed error object, and a
  result shape that the schema allows.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SOLUTION_DIR = Path(__file__).resolve().parents[1]
if str(SOLUTION_DIR) not in sys.path:
    sys.path.insert(0, str(SOLUTION_DIR))

from jsonschema import Draft202012Validator  # noqa: E402

from lambda_rpc.app import create_app  # noqa: E402
from lambda_rpc.service import LambdaService  # noqa: E402

SCHEMA = json.loads((SOLUTION_DIR / "rpc.schema.json").read_text())
Draft202012Validator.check_schema(SCHEMA)


def validator_for(definition: str) -> Draft202012Validator:
    """Validator for ``#/$defs/<definition>`` with the full schema in scope."""
    return Draft202012Validator({**SCHEMA, "oneOf": [{"$ref": f"#/$defs/{definition}"}]})


RESPONSE = validator_for("response")
BATCH_RESPONSE = validator_for("batchResponse")
REQUEST = validator_for("request")

# Things that must never show up in a response body.
LEAK_MARKERS = ("Traceback", 'File "', "/home/", ".py", "lambda3", "D0V", "ENVcns", "object at 0x")

FACTORIAL = (
    "let fact : sint -> sint =\n"
    "  fix fact(n: sint): sint =>\n"
    "    if n <= 1 then 1 else n * fact(n - 1)\n"
    "in fact(6) end"
)
FIB_30 = (
    "let fib : sint -> sint = fix fib(n: sint): sint => "
    "if n < 2 then n else fib(n - 1) + fib(n - 2) in fib(30) end"
)


def request(method: str, params=None, request_id=1, *, notification: bool = False) -> dict:
    req: dict = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        req["params"] = params
    if not notification:
        req["id"] = request_id
    return req


class RpcTestCase(unittest.TestCase):
    """Base class: builds an app with a real LambdaService unless overridden."""

    service_timeout: float = 5.0

    def make_service(self) -> LambdaService:
        return LambdaService(timeout=self.service_timeout)

    def setUp(self) -> None:
        self.service = self.make_service()
        self.client = create_app(self.service).test_client()

    # -- transport -----------------------------------------------------------

    def post_raw(self, body: bytes, content_type: str = "application/json"):
        return self.client.post("/rpc", data=body, content_type=content_type)

    def post(self, payload):
        return self.post_raw(json.dumps(payload).encode("utf-8"))

    def json_reply(self, response):
        """Assert HTTP 200 + JSON media type and return the decoded body."""
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.mimetype, "application/json")
        return json.loads(response.get_data(as_text=True))

    def assert_no_leak(self, error_or_body) -> None:
        text = json.dumps(error_or_body)
        for marker in LEAK_MARKERS:
            self.assertNotIn(marker, text, f"error response leaks {marker!r}")

    def assert_no_reply(self, response) -> None:
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.get_data(), b"")

    # -- JSON-RPC envelopes --------------------------------------------------

    def assert_valid_response(self, body) -> None:
        errors = sorted(RESPONSE.iter_errors(body), key=str)
        self.assertFalse(errors, f"not a valid JSON-RPC response: {body!r}: {errors[:1]}")
        self.assertFalse("result" in body and "error" in body)

    def call(self, method: str, params=None, request_id=1) -> dict:
        body = self.json_reply(self.post(request(method, params, request_id)))
        self.assert_valid_response(body)
        return body

    def assert_result(self, body: dict, request_id) -> dict:
        self.assert_valid_response(body)
        self.assertEqual(body["id"], request_id)
        self.assertIs(type(body["id"]), type(request_id))
        self.assertIn("result", body, body)
        return body["result"]

    def assert_error(self, body: dict, request_id, code: int) -> dict:
        self.assert_valid_response(body)
        self.assertEqual(body["id"], request_id)
        self.assertIn("error", body, body)
        self.assertEqual(body["error"]["code"], code, body)
        self.assert_no_leak(body)
        return body["error"]

    def ok(self, method: str, params=None, request_id=1) -> dict:
        return self.assert_result(self.call(method, params, request_id), request_id)

    def fails(self, method: str, params, code: int, request_id=1) -> dict:
        return self.assert_error(self.call(method, params, request_id), request_id, code)
