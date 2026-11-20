"""Required test 9: a real HTTP client flow over a socket, from open through
all 92 solution events to completion. Also checks the static client routes."""

from __future__ import annotations

import json
import logging
import threading
import unittest
import urllib.error
import urllib.request
from typing import Any

from werkzeug.serving import make_server

from _support import SOLVER, reference_solutions, slow
from queens_rpc.app import create_app
from queens_rpc.service import QueensService


logging.getLogger("werkzeug").setLevel(logging.ERROR)


class LiveServer:
    def __init__(self) -> None:
        self.server = make_server("127.0.0.1", 0, create_app(QueensService(SOLVER)), threaded=True)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.next_id = 0

    def __enter__(self) -> "LiveServer":
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.server.shutdown()
        self.thread.join()

    def get(self, path: str) -> tuple[int, str, bytes]:
        try:
            with urllib.request.urlopen(self.url + path) as r:
                return r.status, r.headers.get_content_type(), r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get_content_type(), e.read()

    def rpc(self, method: str, params: Any) -> Any:
        self.next_id += 1
        req = urllib.request.Request(
            self.url + "/rpc", method="POST", headers={"Content-Type": "application/json"},
            data=json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": self.next_id}).encode())
        with urllib.request.urlopen(req) as r:
            assert r.status == 200 and r.headers.get_content_type() == "application/json"
            body = json.loads(r.read())
        assert body["id"] == self.next_id, body
        return body


class HttpEndToEndTests(unittest.TestCase):
    @slow
    def test_open_through_92_solutions_to_done(self) -> None:
        with LiveServer() as srv:
            self.assertEqual(srv.rpc("service.health", {})["result"]["status"], "ok")
            sid = srv.rpc("queens.open", {"size": 8})["result"]["stream_id"]
            solutions, done_events, calls, done = [], 0, 0, False
            while not done:
                result = srv.rpc("queens.next", {"stream_id": sid, "limit": 32})["result"]
                calls += 1
                self.assertLessEqual(len(result["events"]), 32)
                for e in result["events"]:
                    if e["event"] == "solution":
                        solutions.append(tuple(e["board"]))
                    done_events += e["event"] == "done"
                done = result["done"]
            self.assertEqual(solutions, reference_solutions(8))
            self.assertEqual(len(set(solutions)), 92)
            self.assertEqual(done_events, 1)
            self.assertEqual(calls, -(-33589 // 32))   # incremental: ceil(events / 32) calls
            self.assertEqual(srv.rpc("queens.next", {"stream_id": sid, "limit": 32})["result"],
                             {"events": [], "done": True})
            self.assertEqual(srv.rpc("queens.close", {"stream_id": sid})["result"], {"closed": True})
            self.assertEqual(srv.rpc("queens.next", {"stream_id": sid})["error"]["code"], -32001)

    def test_small_flow_and_static_client(self) -> None:
        with LiveServer() as srv:
            sid = srv.rpc("queens.open", {"size": 4})["result"]["stream_id"]
            first = srv.rpc("queens.next", {"stream_id": sid, "limit": 1})["result"]
            self.assertEqual(first, {"events": [{"event": "try", "column": 0, "row": 0, "board": []}], "done": False})

            status, ctype, page = srv.get("/")
            self.assertEqual((status, ctype), (200, "text/html"))
            for control in (b'id="btn-start"', b'id="btn-step"', b'id="btn-play"', b'id="btn-next"',
                            b'id="btn-reset"', b'id="speed"', b'id="log"', b'id="status"', b'id="banner"'):
                self.assertIn(control, page)
            for asset in ("main.js", "rpc.js", "player.js", "board.js", "events.js", "app.css"):
                self.assertEqual(srv.get("/static/" + asset)[0], 200, asset)
            self.assertEqual(srv.get("/static/../queens_rpc/app.py")[0], 404)
            self.assertEqual(srv.get("/static/missing.js")[0], 404)


if __name__ == "__main__":
    unittest.main()
