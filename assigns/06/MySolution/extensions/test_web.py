"""API tests for the web front-end extension (requires Flask; skipped without it).

Run from assigns/06:
    .venv/bin/python -m unittest discover -s MySolution/extensions -p 'test_*.py'
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "web"))

import importlib.util

HAS_FLASK = importlib.util.find_spec("flask") is not None

if HAS_FLASK:
    from server.app import create_app
    from server.reader import ReadError, read_d0exp
    from server.tools import LanguageTools
    from source_ast import D0Eint, D0Eop2

FACT = "((fix fact(n). (if (n == 0) then 1 else (n * (fact (n - 1))))) 4)"
LOOP = "((fix loop(x). (loop x)) 0)"


class _NoRunner:
    """Interpret is exercised separately; these tests need no child process."""

    def shutdown(self):
        pass


@unittest.skipUnless(HAS_FLASK, "Flask is not installed")
class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(LanguageTools(_NoRunner())).test_client()

    def post(self, op, **payload):
        return self.client.post(f"/api/{op}", json=payload).get_json()

    def compile(self, source, revision=1):
        return self.post("compile", source=source, revision=revision)

    def execute(self, compiled, kind="nat", exec_budget=100_000, obs_budget=100_000):
        return self.post("execute", artifact=compiled["details"]["artifact"],
                         revision=compiled["revision"], kind=kind,
                         execBudget=exec_budget, obsBudget=obs_budget)

    def test_index_served(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"LAMBDA Compiler Workbench", page.data)
        page.close()

    def test_compile_then_execute_factorial(self):
        compiled = self.compile(FACT)
        self.assertEqual(compiled["status"], "ok")
        self.assertTrue(compiled["value"].startswith("("))
        result = self.execute(compiled)
        self.assertEqual((result["status"], result["value"]), ("ok", "24"))
        self.assertGreater(result["details"]["execSteps"], 0)
        self.assertIn("obsSteps", result["details"])

    def test_execute_kinds(self):
        self.assertEqual(self.execute(self.compile("(false or true)"), "bool")["value"], "true")
        pair = self.compile("(pair (pair 2 true) 3)")
        self.assertEqual(self.execute(pair, "((nat, bool), nat)")["value"], "((2, true), 3)")

    def test_loop_exhausts(self):
        result = self.execute(self.compile(LOOP), exec_budget=2_000)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["details"]["execStatus"], "exhausted")
        self.assertEqual(result["details"]["execSteps"], 2_000)
        self.assertIn("not a proof", result["message"])

    def test_wrong_kind_reports_malformed(self):
        result = self.execute(self.compile("2"), "bool")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["details"]["obsStatus"], "malformed")

    def test_compile_errors(self):
        for source in ("(1 / 2)", "-3", "(if true then 1 else (1 % 2))"):
            with self.subTest(source):
                result = self.compile(source)
                self.assertEqual(result["status"], "error")
        self.assertEqual(self.compile("(1 / 2)")["errorKind"], "language")
        self.assertEqual(self.compile("(1 +")["errorKind"], "input")

    def test_open_program_compiles_but_does_not_execute(self):
        compiled = self.compile("(x + 1)")
        self.assertEqual(compiled["status"], "ok")
        self.assertEqual(compiled["details"]["freeVariables"], ["x"])
        result = self.execute(compiled)
        self.assertEqual((result["status"], result["errorKind"]), ("error", "language"))

    def test_execute_rejects_bad_requests(self):
        compiled = self.compile("2")
        stale = self.post("execute", artifact=compiled["details"]["artifact"], revision=2,
                          kind="nat", execBudget=10, obsBudget=10)
        self.assertIn("different source revision", stale["message"])
        bad_kind = self.execute(compiled, kind="string")
        self.assertIn("Result kind", bad_kind["message"])
        bad_budget = self.execute(compiled, exec_budget=-1)
        self.assertIn("budget", bad_budget["message"])
        forged = dict(compiled["details"]["artifact"], code="(x +")
        result = self.post("execute", artifact=forged, revision=1, kind="nat",
                           execBudget=10, obsBudget=10)
        self.assertIn("could not be read", result["message"])
        missing = self.client.post("/api/execute", json={"artifact": None, "revision": 1})
        self.assertEqual(missing.status_code, 400)

    def test_lint(self):
        self.assertEqual(self.post("lint", source=FACT, revision=1)["status"], "ok")
        free = self.post("lint", source="(x + y)", revision=1)
        self.assertEqual(free["details"]["freeVariables"], ["x", "y"])
        self.assertIn("'/'", self.post("lint", source="(1 / 2)", revision=1)["message"])

    def test_reader_accepts_both_notations(self):
        expected = D0Eop2("+", D0Eint(2), D0Eint(3))
        self.assertEqual(read_d0exp("# comment\n(2 + 3)\n"), expected)
        self.assertEqual(read_d0exp('D0Eop2("+", D0Eint(2), D0Eint(3))'), expected)
        self.assertEqual(read_d0exp('D0Eop2("and", D0Eint(2), D0Eint(3))').name, "and")
        with self.assertRaises(ReadError):
            read_d0exp("# only a comment")

    def test_interpret_in_process(self):
        from server.tools import evaluate_source
        self.assertEqual(evaluate_source(FACT)[3], "24")
        self.assertEqual(evaluate_source("(pair 2 true)")[3], "(2, true)")
        self.assertEqual(evaluate_source("(1 / 2)")[2], "runtime")
        self.assertEqual(evaluate_source("(x + 1)")[2], "language")


if __name__ == "__main__":
    unittest.main()
