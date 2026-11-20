"""Required tests 6 and 8 at the RPC level: method results, limits,
exhaustion, close, unknown/expired IDs, cleanup, and validation before
allocation."""

from __future__ import annotations

import unittest

from _support import RpcTestCase, reference_trace, unforced
from queens_rpc.service import STREAM_NOT_FOUND, TOO_MANY_STREAMS

INVALID_PARAMS = -32602


class HealthAndOpenTests(RpcTestCase):
    def test_health(self) -> None:
        self.assertEqual(self.ok("service.health", {}), {"status": "ok", "version": "1.0"})
        self.assertEqual(self.ok("service.health"), {"status": "ok", "version": "1.0"})

    def test_open_returns_id_and_size_without_forcing(self) -> None:
        result = self.ok("queens.open", {"size": 8})
        self.assertEqual(set(result), {"stream_id", "size"})
        self.assertEqual(result["size"], 8)
        entry = self.service.streams._entries[result["stream_id"]]
        self.assertTrue(unforced(entry.stream))
        self.assertEqual(entry.stream.events_emitted, 0)

    def test_accepts_sizes_4_to_10(self) -> None:
        for size in range(4, 11):
            with self.subTest(size=size):
                self.assertEqual(self.ok("queens.open", {"size": size})["size"], size)
                self.service.streams._entries.clear()

    def test_invalid_sizes(self) -> None:
        for bad in (3, 11, 0, -8, 8.0, "8", True, None, [8]):
            with self.subTest(size=bad):
                err = self.fails("queens.open", {"size": bad}, INVALID_PARAMS)
                self.assertEqual(err["data"]["param"], "size")
        self.fails("queens.open", {}, INVALID_PARAMS)

    def test_validation_happens_before_allocation(self) -> None:
        for params in ({"size": 99}, {"size": 8, "extra": 1}, [8], {}):
            self.call("queens.open", params)
        self.assertEqual(len(self.service.streams), 0)

    def test_unexpected_params_rejected(self) -> None:
        err = self.fails("queens.open", {"size": 8, "source": "fix f(x) => f(x)"}, INVALID_PARAMS)
        self.assertEqual(err["data"], {"param": "source", "reason": "unexpected_param"})
        self.fails("service.health", {"x": 1}, INVALID_PARAMS)
        self.fails("queens.next", [], INVALID_PARAMS)


class NextTests(RpcTestCase):
    def test_limit_1_and_32(self) -> None:
        sid = self.open_stream(8)
        expected = reference_trace(8)
        first = self.ok("queens.next", {"stream_id": sid, "limit": 1})
        self.assertEqual(first, {"events": expected[:1], "done": False})
        batch = self.ok("queens.next", {"stream_id": sid, "limit": 32})
        self.assertEqual(batch, {"events": expected[1:33], "done": False})

    def test_limit_defaults_to_1(self) -> None:
        sid = self.open_stream(8)
        self.assertEqual(len(self.ok("queens.next", {"stream_id": sid})["events"]), 1)

    def test_never_more_than_requested(self) -> None:
        sid = self.open_stream(4)
        for limit in (1, 2, 7, 32, 3):
            with self.subTest(limit=limit):
                self.assertLessEqual(len(self.ok("queens.next", {"stream_id": sid, "limit": limit})["events"]), limit)

    def test_invalid_limits(self) -> None:
        sid = self.open_stream(8)
        for bad in (0, 33, -1, 1.5, "1", True, None):
            with self.subTest(limit=bad):
                err = self.fails("queens.next", {"stream_id": sid, "limit": bad}, INVALID_PARAMS)
                self.assertEqual(err["data"]["param"], "limit")
        # A rejected request does not consume events.
        self.assertEqual(self.ok("queens.next", {"stream_id": sid})["events"], reference_trace(8)[:1])

    def test_invalid_stream_id_params(self) -> None:
        for bad in (None, 7, ["x"], "", "x" * 65):
            with self.subTest(stream_id=bad):
                self.fails("queens.next", {"stream_id": bad}, INVALID_PARAMS)
        self.fails("queens.next", {"limit": 1}, INVALID_PARAMS)

    def test_exhaustion_then_repeated_next(self) -> None:
        sid = self.open_stream(4)
        expected = reference_trace(4)
        got, done, responses = [], False, []
        while not done:
            r = self.ok("queens.next", {"stream_id": sid, "limit": 32})
            responses.append(r)
            got += r["events"]
            done = r["done"]
        self.assertEqual(got, expected)
        # Only the response containing `done` says done: true.
        self.assertTrue(all(not r["done"] for r in responses[:-1]))
        self.assertEqual(responses[-1]["events"][-1], {"event": "done"})
        self.assertLess(len(responses[-1]["events"]), 32)      # fewer events when the stream ends
        for _ in range(2):
            self.assertEqual(self.ok("queens.next", {"stream_id": sid, "limit": 32}), {"events": [], "done": True})


class LifecycleTests(RpcTestCase):
    def test_close_then_next_and_close_again(self) -> None:
        sid = self.open_stream()
        self.assertEqual(self.ok("queens.close", {"stream_id": sid}), {"closed": True})
        self.assertEqual(len(self.service.streams), 0)          # cleanup
        err = self.fails("queens.next", {"stream_id": sid}, STREAM_NOT_FOUND)
        self.assertEqual(err["message"], "Unknown stream")
        self.assertEqual(err["data"], {"stream_id": sid, "reason": "unknown_closed_or_expired"})
        self.fails("queens.close", {"stream_id": sid}, STREAM_NOT_FOUND)

    def test_unknown_id(self) -> None:
        self.fails("queens.next", {"stream_id": "not-a-real-stream"}, STREAM_NOT_FOUND)
        self.fails("queens.close", {"stream_id": "00000000-0000-4000-8000-000000000000"}, STREAM_NOT_FOUND)

    def test_expiration(self) -> None:
        sid = self.open_stream()
        self.clock.advance(self.ttl_seconds - 1)
        self.ok("queens.next", {"stream_id": sid})
        self.clock.advance(self.ttl_seconds - 1)
        self.ok("queens.next", {"stream_id": sid})
        self.clock.advance(self.ttl_seconds)
        self.fails("queens.next", {"stream_id": sid}, STREAM_NOT_FOUND)
        self.assertEqual(len(self.service.streams), 0)

    def test_close_exhausted_stream(self) -> None:
        sid = self.open_stream(4)
        while not self.ok("queens.next", {"stream_id": sid, "limit": 32})["done"]:
            pass
        self.assertEqual(self.ok("queens.close", {"stream_id": sid}), {"closed": True})

    def test_too_many_streams(self) -> None:
        for _ in range(self.max_streams):
            self.open_stream()
        err = self.fails("queens.open", {"size": 8}, TOO_MANY_STREAMS)
        self.assertEqual(err["data"], {"limit": self.max_streams})

    def test_streams_are_independent(self) -> None:
        a, b = self.open_stream(5), self.open_stream(5)
        self.ok("queens.next", {"stream_id": a, "limit": 10})
        self.assertEqual(self.ok("queens.next", {"stream_id": b, "limit": 1})["events"], reference_trace(5)[:1])


if __name__ == "__main__":
    unittest.main()
