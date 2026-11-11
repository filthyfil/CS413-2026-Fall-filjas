"""HTTP transport: the single ``POST /rpc`` endpoint (RPC.md section 1).

This layer only deals with HTTP: method, media type, body size, and status
codes. It hands the raw body to the JSON-RPC dispatcher and serializes the
reply. Every JSON-RPC reply, including parse and invalid-request errors, is
HTTP 200. "No reply" (notifications) is HTTP 204. Transport problems use
405/413/415/404 with a plain-text body.
"""

from __future__ import annotations

import json

from flask import Flask, Response, request
from werkzeug.exceptions import HTTPException

from .jsonrpc import Dispatcher
from .service import LambdaService

MAX_BODY_BYTES = 2 * 1024 * 1024


def create_app(service: LambdaService | None = None) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
    dispatcher = Dispatcher((service or LambdaService()).methods())

    @app.post("/rpc")
    def rpc() -> Response:
        if request.mimetype != "application/json":
            return _plain(415, "Unsupported Media Type: use Content-Type: application/json")
        body = request.get_data(cache=False)  # raises 413 above MAX_CONTENT_LENGTH
        reply = dispatcher.handle_body(body)
        if reply is None:
            return Response(status=204)
        return Response(json.dumps(reply), status=200, mimetype="application/json")

    @app.errorhandler(HTTPException)
    def transport_error(error: HTTPException) -> Response:
        # 404 / 405 / 413 and friends: not JSON-RPC responses.
        return _plain(error.code or 500, error.name)

    return app


def _plain(status: int, text: str) -> Response:
    return Response(text + "\n", status=status, mimetype="text/plain")
