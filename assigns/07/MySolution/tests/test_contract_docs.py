"""The documented contract (RPC.md + rpc.schema.json) matches the service.

* The JSON Schema is itself valid and accepts/rejects the right envelopes.
* Every response example in RPC.md is valid under the schema.
* Every request example in RPC.md that is directly followed by its response
  example is replayed against the real service and must produce exactly that
  response (batch responses are compared as unordered collections).
"""

import json
import re
import unittest

from _support import REQUEST, RESPONSE, SOLUTION_DIR, RpcTestCase

RPC_MD = (SOLUTION_DIR / "RPC.md").read_text()
EXAMPLES = [json.loads(block) for block in re.findall(r"```json\n(.*?)```", RPC_MD, re.S)]


def is_response(value) -> bool:
    if isinstance(value, list):
        return bool(value) and all(is_response(v) for v in value)
    return isinstance(value, dict) and "jsonrpc" in value and ("result" in value or "error" in value)


def is_request(value) -> bool:
    return (isinstance(value, list) and not is_response(value)) or (isinstance(value, dict) and "method" in value)


def canonical(value):
    if isinstance(value, list):
        return sorted(json.dumps(v, sort_keys=True) for v in value)
    return value


class SchemaTests(unittest.TestCase):
    def test_schema_accepts_valid_requests(self):
        for req in (
            {"jsonrpc": "2.0", "method": "service.health", "id": 1},
            {"jsonrpc": "2.0", "method": "service.health", "params": {}},
            {"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "1", "libraries": ["list"]}, "id": "a"},
            {"jsonrpc": "2.0", "method": "lambda.compile", "params": {"source": "1", "target": "javascript"}, "id": None},
        ):
            with self.subTest(req=req):
                self.assertTrue(REQUEST.is_valid(req))

    def test_schema_rejects_invalid_requests(self):
        for req in (
            {"jsonrpc": "1.0", "method": "service.health", "id": 1},
            {"jsonrpc": "2.0", "method": "service.health", "id": True},
            {"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "  "}, "id": 1},
            {"jsonrpc": "2.0", "method": "lambda.interpret", "id": 1},
            {"jsonrpc": "2.0", "method": "lambda.compile", "params": {"source": "1", "target": "ruby"}, "id": 1},
            {"jsonrpc": "2.0", "method": "service.health", "id": 1, "extra": 0},
        ):
            with self.subTest(req=req):
                self.assertFalse(REQUEST.is_valid(req))

    def test_schema_rejects_response_with_both_result_and_error(self):
        self.assertFalse(RESPONSE.is_valid({"jsonrpc": "2.0", "result": {"type": "sint"},
                                            "error": {"code": -32603, "message": "x"}, "id": 1}))


class DocumentedExampleTests(RpcTestCase):
    def test_rpc_md_has_examples(self):
        self.assertGreater(len(EXAMPLES), 20)

    def test_documented_responses_match_schema(self):
        for example in filter(is_response, EXAMPLES):
            for response in example if isinstance(example, list) else [example]:
                with self.subTest(response=response):
                    self.assert_valid_response(response)

    def test_documented_request_response_pairs_replay_exactly(self):
        replayed = 0
        for req, expected in zip(EXAMPLES, EXAMPLES[1:]):
            if not (is_request(req) and is_response(expected)):
                continue
            text = json.dumps(expected, ensure_ascii=False)
            if "…" in text or '"slow"' in text:  # abbreviated code / 5-second timeout demo
                continue
            with self.subTest(request=req):
                actual = self.json_reply(self.post(req))
                self.assertEqual(canonical(actual), canonical(expected))
                replayed += 1
        self.assertGreaterEqual(replayed, 12)


if __name__ == "__main__":
    unittest.main()
