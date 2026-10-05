"""HTTP layer: dispatch, request validation and failure reporting."""
import pytest

from server.app import create_app
from server.tools import LanguageTools


class RecordingTools(LanguageTools):
    """Records which entry point was called; can be told to blow up."""

    def __init__(self, explode=False):
        super().__init__()
        self.calls, self.explode = [], explode

    def _rec(self, name, *args):
        self.calls.append((name, *args))
        if self.explode:
            raise RuntimeError("backend exploded")

    def lint(self, source, revision):
        self._rec("lint", source, revision)
        return super().lint(source, revision)

    def interpret(self, source, revision, run_id):
        self._rec("interpret", source, revision, run_id)
        return super().interpret(source, revision, run_id)

    def typecheck(self, source, revision):
        self._rec("typecheck", source, revision)
        return super().typecheck(source, revision)

    def compile(self, source, revision):
        self._rec("compile", source, revision)
        return super().compile(source, revision)

    def execute(self, artifact, revision):
        self._rec("execute", artifact, revision)
        return super().execute(artifact, revision)


@pytest.fixture
def tools():
    t = RecordingTools()
    yield t
    t.shutdown()


@pytest.fixture
def client(tools):
    return create_app(tools).test_client()


SRC = 'D0Eop2("+", D0Eint(20), D0Eint(22))'


@pytest.mark.parametrize("op", ["lint", "typecheck", "compile"])
def test_source_ops_dispatch_to_matching_tool(client, tools, op):
    res = client.post(f"/api/{op}", json={"source": SRC, "revision": 9})
    assert res.status_code == 200
    assert res.json["op"] == op and res.json["revision"] == 9
    assert tools.calls == [(op, SRC, 9)]


def test_interpret_dispatch(client, tools):
    res = client.post("/api/interpret",
                      json={"source": SRC, "revision": 2, "runId": "r1"})
    assert res.json["value"] == "D0Vint(arg1=42)"
    assert tools.calls == [("interpret", SRC, 2, "r1")]


def test_execute_dispatch_and_unavailable(client, tools):
    res = client.post("/api/execute", json={"artifact": None, "revision": 1})
    assert res.status_code == 200
    assert res.json["status"] == "error"
    assert tools.calls == [("execute", None, 1)]


def test_placeholders_never_report_success(client):
    for op in ("typecheck", "compile"):
        res = client.post(f"/api/{op}", json={"source": SRC, "revision": 1})
        assert res.json["status"] == "not_implemented"
        assert res.json["status"] != "ok"


def test_lint_reports_undeclared_variable(client):
    res = client.post("/api/lint", json={"source": 'D0Evar("x")', "revision": 1})
    assert res.json["status"] == "error"
    assert res.json["details"]["freeVariables"] == ["x"]


@pytest.mark.parametrize("payload", [
    None, [], {"revision": 1}, {"source": SRC}, {"source": 3, "revision": 1},
    {"source": SRC, "revision": "1"},
])
def test_bad_requests_are_backend_failures(client, tools, payload):
    res = client.post("/api/lint", json=payload)
    assert res.status_code == 400
    assert res.json["status"] == "failure"
    assert tools.calls == []


def test_interpret_requires_run_id(client):
    res = client.post("/api/interpret", json={"source": SRC, "revision": 1})
    assert res.status_code == 400


def test_unknown_operation(client):
    res = client.post("/api/optimize", json={"source": SRC, "revision": 1})
    assert res.status_code == 400 and res.json["status"] == "failure"


def test_tool_exception_becomes_failure_result():
    tools = RecordingTools(explode=True)
    client = create_app(tools).test_client()
    res = client.post("/api/lint", json={"source": SRC, "revision": 5})
    assert res.status_code == 500
    assert res.json["status"] == "failure"
    assert res.json["errorKind"] == "backend"
    assert res.json["revision"] == 5
    tools.shutdown()


def test_cancel_endpoint(client):
    res = client.post("/api/cancel", json={"runId": "nope"})
    assert res.json == {"runId": "nope", "cancelled": False}
    assert client.post("/api/cancel", json={}).status_code == 400


def test_serves_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"<html" in res.data
