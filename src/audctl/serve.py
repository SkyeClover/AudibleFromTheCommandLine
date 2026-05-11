"""Localhost JSON HTTP API for automation (Home Assistant, scripts, Docker host)."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from audctl.http_api import RouteHandler


def _http_token() -> str:
    return os.environ.get("AUDCTL_HTTP_TOKEN", "").strip()


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    token = _http_token()
    if not token:
        return True
    parsed = urlparse(handler.path)
    p = (parsed.path or "/").rstrip("/") or "/"
    if p in ("/health", "/"):
        return True
    auth = (handler.headers.get("Authorization") or "").strip()
    return auth == f"Bearer {token}"


def make_handler(*, routes: dict[str, RouteHandler]) -> type[BaseHTTPRequestHandler]:
    class AudctlHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:  # noqa: A003
            return

        def _path_key(self) -> str:
            parsed = urlparse(self.path)
            path = parsed.path or "/"
            if len(path) > 1 and path.endswith("/"):
                path = path.rstrip("/")
            return f"{self.command} {path}"

        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _json(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if not _authorized(self):
                self._json(401, {"error": "unauthorized", "hint": "Set Authorization: Bearer <AUDCTL_HTTP_TOKEN>."})
                return
            key = self._path_key()
            handler = routes.get(key)
            if not handler:
                self._json(404, {"error": "not_found", "path": key})
                return
            try:
                result = handler({})
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": "handler_error", "detail": str(exc)})
                return
            self._json(200, result)

        def do_POST(self) -> None:  # noqa: N802
            if not _authorized(self):
                self._json(401, {"error": "unauthorized", "hint": "Set Authorization: Bearer <AUDCTL_HTTP_TOKEN>."})
                return
            key = self._path_key()
            handler = routes.get(key)
            if not handler:
                self._json(404, {"error": "not_found", "path": key})
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._json(400, {"error": "invalid_json"})
                return
            if not isinstance(data, dict):
                self._json(400, {"error": "body_must_be_object"})
                return
            try:
                result = handler(data)
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": "handler_error", "detail": str(exc)})
                return
            self._json(200, result)

    return AudctlHandler


def build_server(
    host: str,
    port: int,
    *,
    routes: dict[str, RouteHandler],
) -> ThreadingHTTPServer:
    handler = make_handler(routes=routes)
    return ThreadingHTTPServer((host, port), handler)
