"""Requirement 8 and the application error classes: backend failures, timeouts,
runtime errors, and stack-limit errors.

Test doubles appear only in this file, and only for failure behavior and the
service/worker dispatch boundary (RPC.md sections 4-5).
"""

import multiprocessing
import time
import unittest
from unittest import mock

from _support import FACTORIAL, FIB_30, RpcTestCase, request

from lambda_rpc import frontend
from lambda_rpc.app import create_app
from lambda_rpc.service import LambdaService
from lambda_rpc import worker

SECRET = "boom in /home/someone/secret/lambda3.py line 42"


class InjectedBackendFailureTests(RpcTestCase):
    """An unexpected exception inside LAMBDA3 becomes -32603 without details."""

    def assert_internal_error(self, method, params, request_id):
        with self.assertLogs("lambda_rpc.jsonrpc", "ERROR") as logs:
            body = self.call(method, params, request_id)
        error = self.assert_error(body, request_id, -32603)
        self.assertEqual(error, {"code": -32603, "message": "Internal error"})
        self.assertNotIn(SECRET, str(body))
        # ...but the server log has the full story.
        logged = "\n".join(logs.output)
        self.assertIn("Traceback", logged)
        self.assertIn(SECRET, logged)

    def test_type_checker_crash(self):
        with mock.patch.object(frontend, "parse_and_typecheck", side_effect=RuntimeError(SECRET)):
            for method, extra in (("lambda.typecheck", {}), ("lambda.interpret", {}),
                                  ("lambda.compile", {"target": "python"})):
                with self.subTest(method=method):
                    self.assert_internal_error(method, {"source": "1 + 2", **extra}, f"crash-{method}")

    def test_compiler_crash(self):
        with mock.patch.object(frontend.L, "d0exp_compile_js", side_effect=KeyError(SECRET)):
            self.assert_internal_error("lambda.compile", {"source": "1 + 2", "target": "javascript"}, 99)

    def test_interpreter_worker_crash(self):
        self.client = create_app(LambdaService(interpreter=lambda *_: worker.InternalFailure())).test_client()
        with self.assertLogs("lambda_rpc.jsonrpc", "ERROR"):
            body = self.call("lambda.interpret", {"source": "1"}, "w")
        self.assertEqual(self.assert_error(body, "w", -32603), {"code": -32603, "message": "Internal error"})

    def test_failing_notification_is_still_silent(self):
        with mock.patch.object(frontend, "parse_and_typecheck", side_effect=RuntimeError(SECRET)):
            with self.assertLogs("lambda_rpc.jsonrpc", "ERROR"):
                self.assert_no_reply(self.post(request("lambda.typecheck", {"source": "1"}, notification=True)))

    def test_crash_in_batch_only_affects_its_member(self):
        real = frontend.parse_and_typecheck

        def flaky(source, libraries=()):
            if source == "crash":
                raise RuntimeError(SECRET)
            return real(source, libraries)

        with mock.patch.object(frontend, "parse_and_typecheck", side_effect=flaky), \
                self.assertLogs("lambda_rpc.jsonrpc", "ERROR"):
            body = self.json_reply(self.post([request("lambda.typecheck", {"source": "crash"}, "bad"),
                                              request("lambda.typecheck", {"source": "1"}, "good")]))
        found = {r["id"]: r for r in body}
        self.assertEqual(found["bad"]["error"], {"code": -32603, "message": "Internal error"})
        self.assertEqual(found["good"]["result"], {"type": "sint"})

    def test_compile_stack_overflow_reports_compile_stage(self):
        with mock.patch.object(frontend.L, "d0exp_compile", side_effect=RecursionError):
            error = self.fails("lambda.compile", {"source": "1", "target": "python"}, -32014, "c")
        self.assertEqual(error["data"], {"stage": "compile", "detail": "Python call stack exhausted"})


class FakeInterpreter:
    """Stands in for worker.interpret at the service/worker boundary."""

    def __init__(self, outcome: worker.Outcome):
        self.outcome = outcome
        self.calls: list[tuple[str, tuple[str, ...], float]] = []

    def __call__(self, source: str, libraries: tuple[str, ...], timeout: float) -> worker.Outcome:
        self.calls.append((source, libraries, timeout))
        return self.outcome


class InjectedTimeoutTests(RpcTestCase):
    def make_service(self):
        self.fake = FakeInterpreter(worker.Timeout())
        return LambdaService(timeout=1.25, interpreter=self.fake)

    def test_timeout_outcome_maps_to_32012_and_preserves_id(self):
        error = self.fails("lambda.interpret", {"source": "1 + 1"}, -32012, "t-1")
        self.assertEqual(error, {"code": -32012, "message": "Execution timeout", "data": {"timeoutSeconds": 1.25}})

    def test_worker_receives_source_libraries_and_deadline(self):
        self.fails("lambda.interpret", {"source": "list_range(1, 3)", "libraries": ["list"]}, -32012)
        self.assertEqual(self.fake.calls, [("list_range(1, 3)", ("list",), 1.25)])

    def test_worker_is_not_started_for_invalid_programs(self):
        self.fails("lambda.interpret", {"source": "if then"}, -32010)
        self.fails("lambda.interpret", {"source": "1 + true"}, -32011)
        self.fails("lambda.interpret", {"source": ""}, -32602)
        self.assertEqual(self.fake.calls, [])

    def test_only_interpret_uses_the_worker(self):
        self.ok("lambda.typecheck", {"source": FACTORIAL})
        self.ok("lambda.compile", {"source": FACTORIAL, "target": "python"})
        self.assertEqual(self.fake.calls, [])

    def test_timeout_in_batch_only_affects_its_member(self):
        body = self.json_reply(self.post([request("lambda.interpret", {"source": "1"}, "slow"),
                                          request("service.health", {}, "health")]))
        found = {r["id"]: r for r in body}
        self.assertEqual(found["slow"]["error"]["code"], -32012)
        self.assertEqual(found["health"]["result"]["status"], "ok")


class RealDeadlineTests(RpcTestCase):
    """The real worker process is terminated at the deadline."""

    service_timeout = 0.5

    def test_slow_program_times_out_and_worker_is_terminated(self):
        start = time.monotonic()
        error = self.fails("lambda.interpret", {"source": FIB_30}, -32012, "fib")
        elapsed = time.monotonic() - start
        self.assertEqual(error["data"], {"timeoutSeconds": 0.5})
        self.assertGreaterEqual(elapsed, 0.5)
        self.assertLess(elapsed, 3.0)
        self.assertEqual(multiprocessing.active_children(), [])

    def test_service_keeps_working_after_a_timeout(self):
        self.fails("lambda.interpret", {"source": FIB_30}, -32012)
        self.assertEqual(self.ok("lambda.interpret", {"source": FACTORIAL}), {"type": "sint", "value": "720"})

    def test_typecheck_and_compile_of_slow_program_are_fast(self):
        start = time.monotonic()
        self.assertEqual(self.ok("lambda.typecheck", {"source": FIB_30}), {"type": "sint"})
        self.ok("lambda.compile", {"source": FIB_30, "target": "python"})
        self.assertLess(time.monotonic() - start, 0.5)


class RuntimeErrorTests(RpcTestCase):
    CASES = [
        ("list_head(list_nil())", "list_head: nonempty list expected"),
        ("list_tail(list_nil())", "list_tail: nonempty list expected"),
        ("optn_get(optn_nil())", "optn_get: nonempty option expected"),
        ("1 / 0", "division by zero"),
        ("let f : sint -> sint = lam (n: sint) => 10 / n in f(0) end", "division by zero"),
    ]

    def test_well_typed_programs_failing_at_run_time(self):
        for source, detail in self.CASES:
            with self.subTest(source=source):
                error = self.fails("lambda.interpret", {"source": source}, -32013, source)
                self.assertEqual(error, {"code": -32013, "message": "LAMBDA runtime error",
                                         "data": {"detail": detail}})


class StackLimitTests(RpcTestCase):
    DEEP_SUM = ("let sum : sint -> sint = fix sum(n: sint): sint => "
                "if n <= 0 then 0 else n + sum(n - 1) in sum({n}) end")

    def assert_stack(self, method, params, stage):
        error = self.fails(method, params, -32014, stage)
        self.assertEqual(error, {"code": -32014, "message": "Stack limit exceeded",
                                 "data": {"stage": stage, "detail": "Python call stack exhausted"}})

    def test_evaluation_stage(self):
        self.assertEqual(self.ok("lambda.interpret", {"source": self.DEEP_SUM.format(n=50)})["value"], "1275")
        self.assert_stack("lambda.interpret", {"source": self.DEEP_SUM.format(n=1000)}, "evaluate")

    def test_parse_stage(self):
        nested = "(" * 300 + "1" + ")" * 300
        for method, extra in (("lambda.typecheck", {}), ("lambda.interpret", {}),
                              ("lambda.compile", {"target": "python"})):
            with self.subTest(method=method):
                self.assert_stack(method, {"source": nested, **extra}, "parse")

    def test_typecheck_stage(self):
        self.assert_stack("lambda.typecheck", {"source": "1" + " + 1" * 1500}, "typecheck")

    def test_stack_errors_are_deterministic_and_not_fatal(self):
        source = self.DEEP_SUM.format(n=1000)
        for _ in range(2):
            self.assert_stack("lambda.interpret", {"source": source}, "evaluate")
        self.assertEqual(self.ok("lambda.interpret", {"source": "2 + 2"})["value"], "4")


if __name__ == "__main__":
    unittest.main()
