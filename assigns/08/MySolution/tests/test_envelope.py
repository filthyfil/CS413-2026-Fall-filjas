"""Required test 7: JSON-RPC IDs, malformed envelopes, unknown methods,
invalid params, notifications, application and internal errors, and the
HTTP transport rules. Also batches (optional feature; see DESIGN.md)."""

from __future__ import annotations

import json
import unittest
from typing import Any

from _support import SOLVER, RpcTestCase, reference_trace, request
from queens_rpc.app import create_app
from queens_rpc.service import QueensService

PARSE, INVALID_REQUEST, NOT_FOUND, INVALID_PARAMS, INTERNAL = -32700, -32600, -32601, -32602, -32603


class RequestIdTests(RpcTestCase):
    def test_ids_preserved_with_type(self) -> None:
        for rid in (1, 0, -5, 2**40, "abc", "", "1", 1.5, None):
            with self.subTest(id=rid):
                body = self.call("service.health", {}, rid)
                self.assertEqual(body["id"], rid)
                self.assertIs(type(body["id"]), type(rid))

    def test_id_preserved_on_errors(self) -> None:
        self.assertEqual(self.call("no.such", {}, "x-7")["id"], "x-7")
        self.assertEqual(self.call("queens.open", {"size": 2}, 42)["id"], 42)
        self.assertEqual(self.call("queens.next", {"stream_id": "nope"}, 9)["id"], 9)


class MalformedEnvelopeTests(RpcTestCase):
    def invalid(self, payload: Any, reason: str) -> None:
        body = self.json_reply(self.post(payload))
        self.assert_envelope(body)
        self.assertIsNone(body["id"])
        self.assertEqual(body["error"]["code"], INVALID_REQUEST, body)
        self.assertEqual(body["error"]["data"]["reason"], reason)

    def test_malformed_envelopes(self) -> None:
        self.invalid(42, "not_an_object")
        self.invalid("hello", "not_an_object")
        self.invalid({"method": "service.health", "id": 1}, "bad_jsonrpc")
        self.invalid({"jsonrpc": "1.0", "method": "service.health", "id": 1}, "bad_jsonrpc")
        self.invalid({"jsonrpc": "2.0", "id": 1}, "bad_method")
        self.invalid({"jsonrpc": "2.0", "method": 5, "id": 1}, "bad_method")
        self.invalid({"jsonrpc": "2.0", "method": "service.health", "id": True}, "bad_id")
        self.invalid({"jsonrpc": "2.0", "method": "service.health", "id": {"a": 1}}, "bad_id")
        self.invalid({"jsonrpc": "2.0", "method": "service.health", "params": 3, "id": 1}, "bad_params")
        self.invalid({"jsonrpc": "2.0", "method": "service.health", "id": 1, "extra": 0}, "unexpected_member")
        self.invalid([], "empty_batch")

    def test_parse_errors(self) -> None:
        for raw in (b"{nope", b"", b'{"jsonrpc": "2.0", "method": "x", "id": NaN}', b"\xff\xfe"):
            with self.subTest(raw=raw):
                body = self.json_reply(self.post_raw(raw))
                self.assertEqual(body["error"]["code"], PARSE)
                self.assertIsNone(body["id"])

    def test_unknown_method(self) -> None:
        for name in ("queens.solve_all", "lambda.interpret", "__init__", "queens.open "):
            with self.subTest(method=name):
                body = self.call(name, {})
                self.assertEqual(body["error"]["code"], NOT_FOUND)


class NotificationTests(RpcTestCase):
    def test_valid_notification_gets_204(self) -> None:
        self.assert_no_reply(self.post(request("service.health", {}, notification=True)))

    def test_notification_errors_are_silent(self) -> None:
        self.assert_no_reply(self.post(request("no.such", {}, notification=True)))
        self.assert_no_reply(self.post(request("queens.open", {"size": 99}, notification=True)))
        self.assert_no_reply(self.post(request("queens.next", {"stream_id": "nope"}, notification=True)))

    def test_next_notification_still_consumes(self) -> None:
        sid = self.open_stream(8)
        self.assert_no_reply(self.post(request("queens.next", {"stream_id": sid, "limit": 3}, notification=True)))
        self.assertEqual(self.ok("queens.next", {"stream_id": sid})["events"], reference_trace(8)[3:4])

    def test_close_notification(self) -> None:
        sid = self.open_stream()
        self.assert_no_reply(self.post(request("queens.close", {"stream_id": sid}, notification=True)))
        self.assertEqual(len(self.service.streams), 0)

    def test_invalid_request_is_answered_even_without_id(self) -> None:
        body = self.json_reply(self.post({"jsonrpc": "2.0", "method": 5}))
        self.assertEqual(body["error"]["code"], INVALID_REQUEST)


class InternalErrorTests(RpcTestCase):
    def test_solver_crash_becomes_internal_error_without_leaks(self) -> None:
        class Broken(type(SOLVER)):  # type: ignore[misc]
            def __init__(self) -> None:
                pass

            def open(self, size: int) -> Any:
                raise RuntimeError(f"secret detail in {__file__}")

        self.client = create_app(QueensService(Broken())).test_client()
        with self.assertLogs("queens_rpc.jsonrpc", "ERROR"):
            body = self.call("queens.open", {"size": 8}, 3)
        self.assertEqual(body["error"], {"code": INTERNAL, "message": "Internal error"})
        self.assertEqual(body["id"], 3)

    def test_no_internal_objects_in_any_response(self) -> None:
        sid = self.open_stream(5)
        for _ in range(5):
            self.assert_no_leak(self.call("queens.next", {"stream_id": sid, "limit": 32}))


class TransportTests(RpcTestCase):
    def test_wrong_content_type(self) -> None:
        response = self.post_raw(json.dumps(request("service.health")), content_type="text/plain")
        self.assertEqual(response.status_code, 415)

    def test_charset_parameter_is_fine(self) -> None:
        response = self.post_raw(json.dumps(request("service.health")), "application/json; charset=utf-8")
        self.assertEqual(response.status_code, 200)

    def test_other_http_methods_and_paths(self) -> None:
        self.assertEqual(self.client.get("/rpc").status_code, 405)
        self.assertEqual(self.client.post("/other", json={}).status_code, 404)

    def test_oversized_body(self) -> None:
        response = self.post_raw(b'{"x": "' + b"a" * 70_000 + b'"}')
        self.assertEqual(response.status_code, 413)

    def test_success_and_errors_are_http_200(self) -> None:
        self.assertEqual(self.post(request("service.health")).status_code, 200)
        self.assertEqual(self.post(request("nope")).status_code, 200)


class BatchTests(RpcTestCase):
    def test_mixed_batch(self) -> None:
        sid = self.open_stream(8)
        body = self.json_reply(self.post([
            request("service.health", {}, 1),
            request("queens.next", {"stream_id": sid, "limit": 2}, 2),
            request("service.health", {}, notification=True),
            {"jsonrpc": "2.0"},
            request("nope", {}, 4),
        ]))
        self.assertEqual([r["id"] for r in body], [1, 2, None, 4])
        self.assertEqual(body[1]["result"]["events"], reference_trace(8)[:2])

    def test_batch_items_on_one_stream_run_in_order(self) -> None:
        sid = self.open_stream(8)
        body = self.json_reply(self.post([request("queens.next", {"stream_id": sid, "limit": 3}, i) for i in range(3)]))
        events = [e for r in body for e in r["result"]["events"]]
        self.assertEqual(events, reference_trace(8)[:9])

    def test_all_notification_batch_gets_204(self) -> None:
        self.assert_no_reply(self.post([request("service.health", {}, notification=True)] * 2))

    def test_batch_size_limit(self) -> None:
        body = self.json_reply(self.post([request("service.health", {}, i) for i in range(26)]))
        self.assertEqual(body["error"]["data"]["reason"], "batch_too_large")


if __name__ == "__main__":
    unittest.main()
