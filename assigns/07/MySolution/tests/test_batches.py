"""Requirement 10: batches, notifications, and request-ID handling."""

import unittest

from _support import BATCH_RESPONSE, RpcTestCase, request

from lambda_rpc.jsonrpc import MAX_BATCH_SIZE


class BatchTests(RpcTestCase):
    def batch(self, payload) -> list:
        body = self.json_reply(self.post(payload))
        self.assertIsInstance(body, list)
        errors = list(BATCH_RESPONSE.iter_errors(body))
        self.assertFalse(errors, f"invalid batch response: {errors[:1]}")
        return body

    @staticmethod
    def by_id(responses: list) -> dict:
        return {r["id"]: r for r in responses}

    def test_mixed_batch_preserves_ids_and_omits_notifications(self):
        responses = self.batch([
            request("lambda.interpret", {"source": "6 * 7"}, "answer"),
            request("lambda.typecheck", {"source": "x + 1"}, 2),
            request("service.health", {}, notification=True),
            request("lambda.compile", {"source": "1", "target": "javascript"}, "js"),
            request("lambda.interpret", {"source": "list_head(list_nil())"}, notification=True),
        ])
        self.assertEqual(len(responses), 3)
        found = self.by_id(responses)
        self.assertEqual(set(found), {"answer", 2, "js"})
        self.assertEqual(found["answer"]["result"], {"type": "sint", "value": "42"})
        self.assertEqual(found[2]["error"]["code"], -32011)
        self.assertEqual(found["js"]["result"]["target"], "javascript")

    def test_each_member_matches_its_own_id(self):
        sources = {f"req-{n}": n for n in range(8)}
        responses = self.batch([request("lambda.interpret", {"source": f"{n} * 10"}, rid)
                                for rid, n in sources.items()])
        for response in responses:
            self.assertEqual(response["result"]["value"], str(sources[response["id"]] * 10))

    def test_invalid_members_get_null_id_errors(self):
        responses = self.batch([
            request("service.health", {}, "ok"),
            "not-a-request-object",
            42,
            {"jsonrpc": "2.0", "method": "service.health", "id": True},   # bad id
            {"jsonrpc": "1.0", "method": "service.health"},                # invalid, no id
        ])
        self.assertEqual(len(responses), 5)
        self.assertEqual(self.by_id(responses)["ok"]["result"], {"status": "ok", "version": "1.0"})
        invalid = [r for r in responses if r["id"] is None]
        self.assertEqual(len(invalid), 4)
        for response in invalid:
            self.assertEqual(response["error"]["code"], -32600)

    def test_member_errors_do_not_affect_other_members(self):
        responses = self.batch([
            request("does.not.exist", {}, "a"),
            request("lambda.interpret", {"source": ""}, "b"),
            request("lambda.interpret", {"source": "if then"}, "c"),
            request("lambda.interpret", {"source": "1 + 1"}, "d"),
        ])
        codes = {r["id"]: r.get("error", {}).get("code") for r in responses}
        self.assertEqual(codes, {"a": -32601, "b": -32602, "c": -32010, "d": None})
        self.assertEqual(self.by_id(responses)["d"]["result"]["value"], "2")

    def test_duplicate_ids_are_answered_individually(self):
        responses = self.batch([request("lambda.interpret", {"source": "1"}, "same"),
                                request("lambda.interpret", {"source": "2"}, "same")])
        self.assertEqual(sorted(r["result"]["value"] for r in responses), ["1", "2"])

    def test_notification_only_batch_returns_204_empty_body(self):
        self.assert_no_reply(self.post([
            request("service.health", {}, notification=True),
            request("lambda.typecheck", {"source": "1 + 2"}, notification=True),
            request("lambda.interpret", {"source": "1 + true"}, notification=True),  # failing notification
        ]))

    def test_empty_batch_is_one_invalid_request_object(self):
        body = self.json_reply(self.post([]))
        self.assertIsInstance(body, dict)
        error = self.assert_error(body, None, -32600)
        self.assertEqual(error["data"]["reason"], "empty_batch")

    def test_oversized_batch_is_rejected_as_a_whole(self):
        body = self.json_reply(self.post([request("service.health", {}, n) for n in range(MAX_BATCH_SIZE + 1)]))
        self.assertIsInstance(body, dict)
        self.assertEqual(self.assert_error(body, None, -32600)["data"]["reason"], "batch_too_large")
        self.assertEqual(len(self.batch([request("service.health", {}, n) for n in range(MAX_BATCH_SIZE)])),
                         MAX_BATCH_SIZE)

    def test_nested_batch_member_is_invalid(self):
        responses = self.batch([[request("service.health", {}, 1)]])
        self.assertEqual(responses[0]["id"], None)
        self.assertEqual(responses[0]["error"]["code"], -32600)


class NotificationTests(RpcTestCase):
    def test_single_notification_returns_204_empty_body(self):
        self.assert_no_reply(self.post(request("service.health", {}, notification=True)))

    def test_failing_notifications_are_silent(self):
        for params in ({"source": "if then"}, {"source": ""}, ["1"]):
            with self.subTest(params=params):
                self.assert_no_reply(self.post(request("lambda.interpret", params, notification=True)))
        self.assert_no_reply(self.post(request("no.such.method", {}, notification=True)))

    def test_null_id_is_a_call_not_a_notification(self):
        body = self.json_reply(self.post(request("service.health", {}, None)))
        self.assert_result(body, None)


if __name__ == "__main__":
    unittest.main()
