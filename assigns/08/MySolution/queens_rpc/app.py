"""HTTP transport: ``POST /rpc`` plus the static browser client.

As in Assign07, this layer only deals with HTTP: method, media type, body
size, and status codes. It hands the raw body to the JSON-RPC dispatcher and
serializes the reply. Every JSON-RPC reply, including parse and
invalid-request errors, is HTTP 200. "No reply" (a notification) is HTTP 204.
Transport problems use 404/405/413/415 with a plain-text body.

``GET /`` serves ``client/index.html`` and ``/static/...`` serves the rest
of ``client/``. Neither route touches the solver.
"""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, Response, request, send_from_directory
from werkzeug.exceptions import HTTPException

from .jsonrpc import Dispatcher
from .service import QueensService

MAX_BODY_BYTES = 64 * 1024   # requests are tiny; nothing legitimate comes close
CLIENT_DIR = Path(__file__).resolve().parents[1] / "client"


def create_app(service: QueensService | None = None) -> Flask:
    app = Flask(__name__, static_folder=str(CLIENT_DIR), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
    app.extensions["queens_service"] = service = service or QueensService()
    dispatcher = Dispatcher(service.methods())

    @app.post("/rpc")
    def rpc() -> Response:
        if request.mimetype != "application/json":
            return _plain(415, "Unsupported Media Type: use Content-Type: application/json")
        body = request.get_data(cache=False)  # raises 413 above MAX_CONTENT_LENGTH
        reply = dispatcher.handle_body(body)
        if reply is None:
            return Response(status=204)
        response = Response(json.dumps(reply), status=200, mimetype="application/json")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index() -> Response:
        return send_from_directory(CLIENT_DIR, "index.html")

    @app.errorhandler(HTTPException)
    def transport_error(error: HTTPException) -> Response:
        # 404 / 405 / 413 and friends: not JSON-RPC responses.
        return _plain(error.code or 500, error.name)

    return app


def _plain(status: int, text: str) -> Response:
    return Response(text + "\n", status=status, mimetype="text/plain")
