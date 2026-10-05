"""HTTP layer: serves web/ and exposes LanguageTools as JSON endpoints.

This module only translates HTTP <-> Python calls. It holds no application
state (that is the browser-side Model) and no language logic (tools.py).
"""
from pathlib import Path

from flask import Flask, jsonify, request

from .tools import LanguageTools, make_result

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
SOURCE_OPS = ("lint", "typecheck", "compile")


class BadRequest(Exception):
    pass


def create_app(tools: LanguageTools | None = None) -> Flask:
    app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="")
    app.config["TOOLS"] = tools or LanguageTools()
    # JSON escaping can make the 1 MB source limit larger on the wire.
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

    def tools_() -> LanguageTools:
        return app.config["TOOLS"]

    def body() -> dict:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise BadRequest("expected a JSON object")
        return data

    def field(data: dict, name: str, kind: type):
        value = data.get(name)
        if type(value) is not kind:
            raise BadRequest(f"field {name!r} must be {kind.__name__}")
        return value

    def answer(op: str, data: dict | None, call):
        revision = data.get("revision") if isinstance(data, dict) else None
        try:
            return jsonify(call())
        except BadRequest as exc:
            res = make_result(op, revision, "failure", f"Bad request: {exc}",
                              error_kind="backend")
            return jsonify(res), 400
        except Exception as exc:  # unexpected bug in the tools
            app.logger.exception("%s failed", op)
            res = make_result(op, revision, "failure",
                              f"Internal error: {type(exc).__name__}: {exc}",
                              error_kind="backend")
            return jsonify(res), 500

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.post("/api/<op>")
    def source_op(op: str):
        data = request.get_json(silent=True)
        if op not in SOURCE_OPS:
            return answer(op, data, lambda: _raise(BadRequest(
                f"unknown operation {op!r}")))

        def call():
            d = body()
            return getattr(tools_(), op)(field(d, "source", str),
                                         field(d, "revision", int))
        return answer(op, data, call)

    @app.post("/api/interpret")
    def interpret():
        data = request.get_json(silent=True)

        def call():
            d = body()
            return tools_().interpret(field(d, "source", str),
                                      field(d, "revision", int),
                                      field(d, "runId", str))
        return answer("interpret", data, call)

    @app.post("/api/execute")
    def execute():
        data = request.get_json(silent=True)

        def call():
            d = body()
            artifact = d.get("artifact")
            if artifact is not None and not isinstance(artifact, dict):
                raise BadRequest("field 'artifact' must be an object or null")
            return tools_().execute(artifact, field(d, "revision", int))
        return answer("execute", data, call)

    @app.post("/api/cancel")
    def cancel():
        data = body_or_none()
        if data is None or type(data.get("runId")) is not str:
            return jsonify({"error": "field 'runId' must be str"}), 400
        return jsonify({"runId": data["runId"],
                        "cancelled": tools_().cancel(data["runId"])})

    def body_or_none():
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else None

    return app


def _raise(exc: Exception):
    raise exc
