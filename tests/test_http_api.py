import json
import threading
import urllib.error
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from audctl.config import AudctlConfig
from audctl.http_api import build_routes
from audctl.serve import build_server


def _read_json(url: str, method: str = "GET", data: bytes | None = None) -> tuple[int, dict]:
    req = Request(url, method=method, data=data)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=5) as resp:  # noqa: S310 — test server only
        body = resp.read().decode()
        return resp.getcode() or 200, json.loads(body)


def test_http_api_routes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    cfg = AudctlConfig.load()
    cfg.ensure_private_dirs()
    routes = build_routes(cfg)
    httpd = build_server("127.0.0.1", 0, routes=routes)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        code, data = _read_json(f"{base}/health")
        assert code == 200
        assert data["status"] == "ok"

        code, data = _read_json(f"{base}/v1/status")
        assert code == 200
        assert "library_items" in data

        code, data = _read_json(
            f"{base}/v1/resolve",
            "POST",
            json.dumps({"title": "Some Book"}).encode(),
        )
        assert code == 200
        assert data["ok"] is True
        assert "result" in data
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def test_http_api_bearer_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("AUDCTL_HTTP_TOKEN", "secret-test-token")
    cfg = AudctlConfig.load()
    cfg.ensure_private_dirs()
    routes = build_routes(cfg)
    httpd = build_server("127.0.0.1", 0, routes=routes)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            _read_json(f"{base}/v1/status")
        assert excinfo.value.code == 401

        req = Request(
            f"{base}/v1/status",
            headers={"Authorization": "Bearer secret-test-token"},
        )
        with urlopen(req, timeout=5) as resp:
            assert (resp.getcode() or 200) == 200

        code, data = _read_json(f"{base}/health")
        assert code == 200
        assert data["status"] == "ok"
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def test_http_api_stop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    cfg = AudctlConfig.load()
    cfg.ensure_private_dirs()
    routes = build_routes(cfg)
    httpd = build_server("127.0.0.1", 0, routes=routes)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        code, data = _read_json(
            f"{base}/v1/stop",
            "POST",
            json.dumps({"signal": "term"}).encode(),
        )
        assert code == 200
        assert data["ok"] is True
        assert "stopped" in data
        assert "log" in data
    finally:
        httpd.shutdown()
        thread.join(timeout=2)
