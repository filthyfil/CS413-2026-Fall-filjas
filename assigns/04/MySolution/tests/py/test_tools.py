"""Real Lint and Interpret through the language-tool adapter."""
import threading
import time

import pytest

from server import lambda1, tools
from server.runner import InterpretRunner
from server.tools import LanguageTools, evaluate_source, lint_source


def fact(n):
    return ('D0Eapp(D0Efix("fact", "n", D0Eif0(D0Eop2("<=", D0Evar("n"), '
            'D0Eint(0)), D0Eint(1), D0Eop2("*", D0Evar("n"), D0Eapp('
            'D0Evar("fact"), D0Eop2("-", D0Evar("n"), D0Eint(1)))))), '
            f'D0Eint({n}))')


def fib(n):
    return ('D0Eapp(D0Efix("fib", "n", D0Eif0(D0Eop2("<", D0Evar("n"), '
            'D0Eint(2)), D0Evar("n"), D0Eop2("+", D0Eapp(D0Evar("fib"), '
            'D0Eop2("-", D0Evar("n"), D0Eint(1))), D0Eapp(D0Evar("fib"), '
            f'D0Eop2("-", D0Evar("n"), D0Eint(2)))))), D0Eint({n}))')


# ---- Lint -------------------------------------------------------------

def test_lint_closed_program_passes(sample):
    status, message, kind, details = lint_source(sample("factorial"))
    assert (status, kind) == ("ok", None)
    assert message == "No free variables found."
    assert details["freeVariables"] == []


def test_lint_open_program_lists_names_sorted():
    src = 'D0Eapp(D0Evar("zeta"), D0Epair(D0Evar("alpha"), D0Evar("zeta")))'
    status, message, kind, details = lint_source(src)
    assert (status, kind) == ("error", "language")
    assert details["freeVariables"] == ["alpha", "zeta"]
    assert message == "Undeclared variable(s): alpha, zeta"


def test_lint_let_initializer_scope(sample):
    status, _, _, details = lint_source(sample("let_scope"))
    assert status == "error" and details["freeVariables"] == ["y"]


def test_lint_does_not_evaluate(sample, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("lint must not evaluate")
    monkeypatch.setattr(lambda1, "d0exp_evaluate", boom)
    status, _, _, _ = lint_source(sample("div_zero"))
    assert status == "ok"   # would raise ZeroDivisionError if evaluated


def test_lint_invalid_input():
    status, message, kind, _ = lint_source("D0Eint(")
    assert (status, kind) == ("error", "input")
    assert message.startswith("Invalid input:")


# ---- Interpret (in process) ---------------------------------------------

@pytest.mark.parametrize("src, value", [
    ('D0Eop2("+", D0Eint(20), D0Eint(22))', "D0Vint(arg1=42)"),
    ('D0Eop2("-", D0Eint(2), D0Eint(5))', "D0Vint(arg1=-3)"),
    ('D0Eop2("*", D0Eint(6), D0Eint(7))', "D0Vint(arg1=42)"),
    ('D0Eop2("/", D0Eint(85), D0Eint(2))', "D0Vint(arg1=42)"),
    ('D0Eop1("+1", D0Eint(41))', "D0Vint(arg1=42)"),
    ('D0Eop2("<", D0Eint(1), D0Eint(2))', "D0Vbtf(arg1=True)"),
    ('D0Epfst(D0Epair(D0Eint(1), D0Ebtf(False)))', "D0Vint(arg1=1)"),
    ('D0Elet("x", D0Eint(5), D0Evar("x"))', "D0Vint(arg1=5)"),
    (fact(0), "D0Vint(arg1=1)"),
    (fact(1), "D0Vint(arg1=1)"),
    (fact(5), "D0Vint(arg1=120)"),
    (fact(10), "D0Vint(arg1=3628800)"),
    (fib(0), "D0Vint(arg1=0)"),
    (fib(1), "D0Vint(arg1=1)"),
    (fib(2), "D0Vint(arg1=1)"),
    (fib(15), "D0Vint(arg1=610)"),
])
def test_interpret_values(src, value):
    assert evaluate_source(src) == ("ok", "Evaluation succeeded.", None, value)


def test_interpret_samples(sample):
    assert evaluate_source(sample("factorial"))[3] == "D0Vint(arg1=3628800)"
    assert evaluate_source(sample("fibonacci"))[3] == "D0Vint(arg1=610)"


def test_interpret_malformed_input_is_input_error(sample):
    for name in ("malformed", "not_allowed"):
        status, message, kind, value = evaluate_source(sample(name))
        assert (status, kind, value) == ("error", "input", None)


@pytest.mark.parametrize("name, exc", [("div_zero", "ZeroDivisionError"),
                                       ("type_error", "TypeError")])
def test_interpret_runtime_failures(sample, name, exc):
    assert lint_source(sample(name))[0] == "ok"     # passes Lint ...
    status, message, kind, _ = evaluate_source(sample(name))
    assert (status, kind) == ("error", "runtime")   # ... but fails at runtime
    assert exc in message


def test_error_sentinel_is_an_error():
    status, _, kind, value = evaluate_source('D0Evar("x")')
    assert (status, kind, value) == ("error", "runtime", "D0V000()")


def test_error_sentinel_inside_pair_is_an_error():
    status, _, kind, value = evaluate_source(
        'D0Epair(D0Eint(1), D0Epair(D0Evar("y"), D0Eint(2)))')
    assert (status, kind) == ("error", "runtime")
    assert "D0V000()" in value


# ---- Interpret through the child-process runner -------------------------

@pytest.fixture(scope="module")
def lt():
    t = LanguageTools()
    yield t
    t.shutdown()


def test_runner_interprets_with_revision(lt, sample):
    res = lt.interpret(sample("fibonacci"), 7, "fib-run")
    assert res == {"op": "interpret", "revision": 7, "status": "ok",
                   "message": "Evaluation succeeded.", "errorKind": None,
                   "value": "D0Vint(arg1=610)", "details": {}}


def test_runner_has_deep_recursion_room(lt):
    res = lt.interpret(fact(3000), 1, "deep")
    assert res["status"] == "ok"
    assert len(res["value"]) > 4300   # bigger than Python's default limit


def test_runner_cancel_stops_infinite_loop_and_allows_retry(lt, sample):
    out = {}
    t = threading.Thread(target=lambda: out.update(
        res=lt.interpret(sample("infinite_loop"), 3, "loop")))
    t.start()
    deadline = time.time() + 10
    while "loop" not in lt.runner.active_runs() and time.time() < deadline:
        time.sleep(0.02)
    time.sleep(0.3)
    assert t.is_alive()                   # still looping
    assert lt.cancel("loop") is True
    t.join(10)
    assert not t.is_alive()
    assert out["res"]["status"] == "cancelled"
    assert out["res"]["revision"] == 3
    assert lt.runner.active_runs() == []
    # retry after the stop works
    assert lt.interpret(fact(4), 3, "retry")["value"] == "D0Vint(arg1=24)"


def test_new_run_stops_an_abandoned_run(lt, sample):
    out = {}
    t = threading.Thread(target=lambda: out.update(
        res=lt.interpret(sample("infinite_loop"), 1, "abandoned")))
    t.start()
    deadline = time.time() + 10
    while "abandoned" not in lt.runner.active_runs() and time.time() < deadline:
        time.sleep(0.02)
    assert lt.interpret(fact(3), 2, "next")["value"] == "D0Vint(arg1=6)"
    t.join(10)
    assert out["res"]["status"] == "cancelled"


def test_cancel_unknown_run_returns_false(lt):
    assert lt.cancel("nothing-running") is False


def test_cancel_that_arrives_early_is_honoured():
    t = LanguageTools(InterpretRunner())
    assert t.cancel("early") is False
    assert t.interpret(fact(3), 1, "early")["status"] == "cancelled"


def test_child_crash_is_backend_failure(monkeypatch):
    class CrashRunner(InterpretRunner):
        def run(self, source, run_id):
            from server.runner import RunOutcome
            return RunOutcome(crash="exit code -9")
    res = LanguageTools(CrashRunner()).interpret("D0Eint(1)", 2, "c")
    assert (res["status"], res["errorKind"]) == ("failure", "backend")


# ---- Placeholders ---------------------------------------------------------

def test_typecheck_and_compile_are_not_implemented(lt):
    tc = lt.typecheck("D0Eint(1)", 4)
    co = lt.compile("D0Eint(1)", 4)
    assert tc["status"] == co["status"] == "not_implemented"
    assert tc["message"] == "Type checking is not yet implemented."
    assert co["message"] == "Compilation is not yet implemented."
    assert "artifact" not in co["details"]


def test_execute_without_artifact_is_unavailable(lt):
    res = lt.execute(None, 4)
    assert res["status"] == "error"
    assert "no generated artifact" in res["message"].lower()


def test_execute_rejects_stale_artifact(lt):
    res = lt.execute({"revision": 3, "format": "x", "code": ""}, 4)
    assert res["status"] == "error" and "different source revision" in res["message"]
