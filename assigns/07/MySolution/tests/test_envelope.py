"""Requirement 6: malformed JSON, invalid envelopes, unknown methods, bad params,
and HTTP transport behavior."""

import json
import unittest

from _support import RpcTestCase, request

from lambda_rpc.service import MAX_SOURCE_BYTES


class ParseErrorTests(RpcTestCase):
    def assert_parse_error(self, raw: bytes, reason: str):
        body = self.json_reply(self.post_raw(raw))
        error = self.assert_error(body, None, -32700)
        self.assertEqual(error["data"], {"reason": reason})

    def test_malformed_json(self):
        for raw in (b'{"jsonrpc":', b"", b"{'single': 'quotes'}", b"[1, 2", b"nul"):
            with self.subTest(raw=raw):
                self.assert_parse_error(raw, "invalid_json")

    def test_non_standard_json_constants(self):
        self.assert_parse_error(b'{"jsonrpc": "2.0", "method": "service.health", "id": NaN}', "invalid_json")

    def test_invalid_utf8(self):
        self.assert_parse_error(b'{"jsonrpc": "2.0", "method": "\xff", "id": 1}', "invalid_utf8")


class InvalidRequestTests(RpcTestCase):
    def assert_invalid(self, payload, reason: str):
        body = self.json_reply(self.post(payload))
        error = self.assert_error(body, None, -32600)  # id is always null
        self.assertEqual(error["data"]["reason"], reason)
        return error

    def test_non_object_requests(self):
        for payload in (42, "service.health", None, True):
            with self.subTest(payload=payload):
                self.assert_invalid(payload, "not_an_object")

    def test_bad_jsonrpc_version(self):
        for version in ("1.0", 2.0, None):
            with self.subTest(version=version):
                self.assert_invalid({"jsonrpc": version, "method": "service.health", "id": 1}, "bad_jsonrpc")
        self.assert_invalid({"method": "service.health", "id": 1}, "bad_jsonrpc")

    def test_bad_method(self):
        self.assert_invalid({"jsonrpc": "2.0", "id": 1}, "bad_method")
        self.assert_invalid({"jsonrpc": "2.0", "method": 5, "id": 1}, "bad_method")

    def test_bad_id_types_get_null_id(self):
        for bad_id in (True, False, {"a": 1}, [1]):
            with self.subTest(id=bad_id):
                self.assert_invalid({"jsonrpc": "2.0", "method": "service.health", "id": bad_id}, "bad_id")

    def test_non_structured_params(self):
        for params in ("source", 1, True, None):
            with self.subTest(params=params):
                self.assert_invalid({"jsonrpc": "2.0", "method": "service.health", "params": params, "id": 1},
                                    "bad_params")

    def test_unexpected_member(self):
        error = self.assert_invalid({**request("service.health", {}), "extra": 0}, "unexpected_member")
        self.assertEqual(error["data"]["member"], "extra")

    def test_invalid_request_without_id_still_gets_a_response(self):
        self.assert_invalid({"jsonrpc": "1.0", "method": "service.health"}, "bad_jsonrpc")


class MethodNotFoundTests(RpcTestCase):
    def test_unknown_method(self):
        error = self.fails("does.not.exist", {}, -32601, "unknown")
        self.assertEqual(error["data"], {"method": "does.not.exist"})

    def test_method_names_are_case_sensitive(self):
        for name in ("Service.Health", "LAMBDA.INTERPRET", "lambda.Interpret", " service.health"):
            with self.subTest(name=name):
                self.fails(name, {}, -32601)


class InvalidParamsTests(RpcTestCase):
    def assert_invalid_params(self, method, params, param, reason, request_id="p"):
        error = self.fails(method, params, -32602, request_id)
        self.assertEqual(error["message"], "Invalid params")
        self.assertEqual((error["data"]["param"], error["data"]["reason"]), (param, reason))
        return error

    def test_absent_params_for_source_methods(self):
        for method in ("lambda.typecheck", "lambda.interpret", "lambda.compile"):
            with self.subTest(method=method):
                self.assert_invalid_params(method, None, "source", "missing")
                self.assert_invalid_params(method, {}, "source", "missing")

    def test_array_params_are_rejected(self):
        self.assert_invalid_params("lambda.interpret", ["1 + 2"], "params", "not_an_object")
        self.assert_invalid_params("service.health", [], "params", "not_an_object")

    def test_wrongly_typed_source(self):
        for source in (12, None, ["1"], {"code": "1"}, True):
            with self.subTest(source=source):
                self.assert_invalid_params("lambda.interpret", {"source": source}, "source", "wrong_type")

    def test_blank_source(self):
        for source in ("", " ", "\n\t  \n"):
            with self.subTest(source=source):
                self.assert_invalid_params("lambda.typecheck", {"source": source}, "source", "blank")

    def test_oversized_source(self):
        at_limit = "1" + " " * (MAX_SOURCE_BYTES - 1)
        self.ok("lambda.typecheck", {"source": at_limit})
        error = self.assert_invalid_params("lambda.typecheck", {"source": at_limit + " "}, "source", "too_large")
        self.assertEqual((error["data"]["limitBytes"], error["data"]["actualBytes"]),
                         (MAX_SOURCE_BYTES, MAX_SOURCE_BYTES + 1))

    def test_source_limit_counts_utf8_bytes_not_characters(self):
        source = "1 #" + "é" * (MAX_SOURCE_BYTES // 2)  # fewer chars than the limit, more bytes
        self.assertLess(len(source), MAX_SOURCE_BYTES)
        self.assert_invalid_params("lambda.typecheck", {"source": source}, "source", "too_large")

    def test_unknown_param_names(self):
        self.assert_invalid_params("lambda.interpret", {"source": "1", "verbose": True}, "verbose", "unexpected_param")
        self.assert_invalid_params("service.health", {"x": 1}, "x", "unexpected_param")
        self.assert_invalid_params("lambda.interpret", {"source": "1", "target": "python"}, "target",
                                   "unexpected_param")

    def test_compile_target(self):
        self.assert_invalid_params("lambda.compile", {"source": "1"}, "target", "missing")
        self.assert_invalid_params("lambda.compile", {"source": "1", "target": 3}, "target", "wrong_type")
        for target in ("ruby", "Python", "js", ""):
            with self.subTest(target=target):
                error = self.assert_invalid_params("lambda.compile", {"source": "1", "target": target},
                                                   "target", "unsupported_target")
                self.assertEqual(error["data"]["allowed"], ["python", "javascript"])

    def test_libraries(self):
        def lib(value):
            return {"source": "1", "libraries": value}
        self.assert_invalid_params("lambda.interpret", lib("list"), "libraries", "wrong_type")
        self.assert_invalid_params("lambda.interpret", lib([1]), "libraries", "wrong_type")
        self.assert_invalid_params("lambda.interpret", lib(["nope"]), "libraries", "unknown_library")
        self.assert_invalid_params("lambda.interpret", lib(["../etc/passwd"]), "libraries", "unknown_library")
        self.assert_invalid_params("lambda.interpret", lib(["list", "list"]), "libraries", "duplicate_library")

    def test_params_checked_before_source_is_parsed(self):
        # Bad target is reported even though the source also has a syntax error.
        self.assert_invalid_params("lambda.compile", {"source": "if then", "target": "ruby"}, "target",
                                   "unsupported_target")


class TransportTests(RpcTestCase):
    HEALTH = json.dumps(request("service.health", {})).encode()

    def test_charset_parameter_is_accepted(self):
        body = self.json_reply(self.post_raw(self.HEALTH, "application/json; charset=utf-8"))
        self.assert_result(body, 1)

    def test_wrong_media_type_is_415(self):
        for content_type in ("text/plain", "application/x-www-form-urlencoded", "application/json-rpc"):
            with self.subTest(content_type=content_type):
                response = self.post_raw(self.HEALTH, content_type)
                self.assertEqual(response.status_code, 415)
                self.assertNotEqual(response.mimetype, "application/json")

    def test_missing_media_type_is_415(self):
        response = self.client.post("/rpc", data=self.HEALTH)
        self.assertEqual(response.status_code, 415)

    def test_other_http_methods_are_405(self):
        for method in (self.client.get, self.client.put, self.client.delete):
            with self.subTest(method=method.__name__):
                self.assertEqual(method("/rpc").status_code, 405)

    def test_operations_are_not_resource_urls(self):
        for path in ("/", "/typecheck", "/lambda.interpret", "/rpc/lambda.compile"):
            with self.subTest(path=path):
                self.assertEqual(self.post_raw(self.HEALTH).status_code, 200)
                self.assertEqual(self.client.post(path, data=self.HEALTH, content_type="application/json")
                                 .status_code, 404)

    def test_oversized_body_is_413(self):
        response = self.post_raw(b" " * (2 * 1024 * 1024 + 1))
        self.assertEqual(response.status_code, 413)

    def test_rpc_errors_use_http_200(self):
        for raw in (b"not json", b"[]", json.dumps(request("nope.nope", {})).encode()):
            with self.subTest(raw=raw):
                self.assertEqual(self.post_raw(raw).status_code, 200)


if __name__ == "__main__":
    unittest.main()
