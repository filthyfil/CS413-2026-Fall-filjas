"""Required test 6 (table level): exhaustion, repeated take, close, unknown
IDs, cleanup, expiry, limits, atomicity, and per-stream serialization."""

from __future__ import annotations

import re
import threading
import unittest
from typing import Any
from unittest import mock

from _support import SOLVER, FakeClock, reference_trace
from queens_rpc import solver as S  # noqa: E402 (after _support sets sys.path)
from queens_rpc.streams import StreamNotFound, StreamTable, TableFull

UUID4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


class StreamTableTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.table = StreamTable(ttl_seconds=60, max_streams=3, clock=self.clock)

    def test_ids_are_distinct_uuid4(self) -> None:
        ids = {self.table.add(SOLVER.open(4)) for _ in range(3)}
        self.assertEqual(len(ids), 3)
        for sid in ids:
            self.assertRegex(sid, UUID4)

    def test_exhaustion_releases_solver_state_and_repeats_done(self) -> None:
        sid = self.table.add(SOLVER.open(4))
        total = len(reference_trace(4))
        seen = []
        done = False
        while not done:
            events, done = self.table.take(sid, 32)
            seen.extend(events)
        self.assertEqual(len(seen), total)
        self.assertEqual(seen[-1], {"event": "done"})
        entry = self.table._entries[sid]
        self.assertIsNone(entry.stream.cursor)          # lazy stream dropped
        for _ in range(3):
            self.assertEqual(self.table.take(sid, 32), ([], True))

    def test_close_and_unknown(self) -> None:
        sid = self.table.add(SOLVER.open(4))
        self.table.close(sid)
        self.assertNotIn(sid, self.table)
        with self.assertRaises(StreamNotFound):
            self.table.take(sid, 1)
        with self.assertRaises(StreamNotFound):
            self.table.close(sid)
        with self.assertRaises(StreamNotFound):
            self.table.take("00000000-0000-4000-8000-000000000000", 1)

    def test_expiry_after_inactivity(self) -> None:
        sid = self.table.add(SOLVER.open(4))
        self.clock.advance(59.9)
        self.table.take(sid, 1)                         # activity refreshes the timer
        self.clock.advance(59.9)
        self.assertEqual(len(self.table.take(sid, 1)[0]), 1)
        self.clock.advance(60)
        with self.assertRaises(StreamNotFound):
            self.table.take(sid, 1)
        self.assertEqual(len(self.table), 0)            # swept, not just hidden

    def test_purge_expired_cleans_up(self) -> None:
        a = self.table.add(SOLVER.open(4))
        self.clock.advance(30)
        b = self.table.add(SOLVER.open(4))
        self.clock.advance(31)
        self.assertEqual(self.table.purge_expired(), [a])
        self.assertIn(b, self.table)

    def test_max_streams_and_sweep_before_limit(self) -> None:
        for _ in range(3):
            self.table.add(SOLVER.open(4))
        with self.assertRaises(TableFull):
            self.table.add(SOLVER.open(4))
        self.clock.advance(61)
        self.table.add(SOLVER.open(4))                  # expired entries made room
        self.assertEqual(len(self.table), 1)

    def test_failed_take_does_not_advance(self) -> None:
        sid = self.table.add(SOLVER.open(4))
        first, _ = self.table.take(sid, 2)
        real_force = S.force
        calls = {"n": 0}

        def flaky(strm: Any) -> Any:
            calls["n"] += 1
            if calls["n"] == 3:
                raise RuntimeError("injected failure mid-batch")
            return real_force(strm)

        with mock.patch.object(S, "force", flaky):
            with self.assertRaises(RuntimeError):
                self.table.take(sid, 5)
        retry, _ = self.table.take(sid, 5)
        self.assertEqual(first + retry, reference_trace(4)[:7])   # nothing skipped or repeated

    def test_concurrent_takes_on_one_stream_are_serialized(self) -> None:
        table = StreamTable(ttl_seconds=60, max_streams=3)
        sid = table.add(SOLVER.open(6))
        results: list[list[dict[str, Any]]] = []
        lock = threading.Lock()

        def worker() -> None:
            for _ in range(10):
                events, _ = table.take(sid, 5)
                with lock:
                    results.append(events)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Every batch is a contiguous slice and the union is the exact prefix.
        expected = reference_trace(6)[:200]
        batches = sorted(results, key=lambda b: expected.index(b[0]))
        flat = [e for b in batches for e in b]
        self.assertEqual(flat, expected)


if __name__ == "__main__":
    unittest.main()
