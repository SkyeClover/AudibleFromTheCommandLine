"""JSON HTTP routes for ``audctl serve`` (localhost automation; not authenticated by default)."""

from __future__ import annotations

from typing import Any, Callable

from audctl import __version__
from audctl.asin import validate_asin
from audctl.auth_setup import load_authenticator
from audctl.config import AudctlConfig
from audctl.db import connect, count as db_count, init_schema
from audctl.library_resolve import resolve_from_library_index
from audctl.library_sync import sync_library_to_db
from audctl.paths import auth_credentials_path, library_db_path
from audctl.play import launch_web_player
from audctl.resolve import resolve_from_asin, resolve_title
from audctl.session import session_status
from audctl.urls import webplayer_url

RouteHandler = Callable[[dict[str, Any]], dict[str, Any]]


def build_routes(cfg: AudctlConfig) -> dict[str, RouteHandler]:
    """Map ``METHOD /path`` (no query string) to handlers. GET handlers receive ``{}``."""

    def get_index(_body: dict[str, Any]) -> dict[str, Any]:
        return {
            "service": "audctl",
            "version": __version__,
            "endpoints": [
                {"method": "GET", "path": "/health", "description": "Liveness check."},
                {"method": "GET", "path": "/", "description": "This discovery document."},
                {"method": "GET", "path": "/v1/status", "description": "Paths, credentials, library row count."},
                {"method": "POST", "path": "/v1/play", "description": "Open web player for an ASIN (JSON body)."},
                {"method": "POST", "path": "/v1/sync", "description": "Refresh library index from Audible API."},
                {"method": "POST", "path": "/v1/resolve", "description": "Resolve title or ASIN to URLs (JSON body)."},
            ],
        }

    def get_health(_body: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "service": "audctl", "version": __version__}

    def get_status(_body: dict[str, Any]) -> dict[str, Any]:
        info = session_status(
            host=cfg.audible_host,
            profile_dir=cfg.chromium_profile_dir,
            chromium_binary=cfg.chromium_binary,
        )
        info["version"] = __version__
        info["marketplace_country"] = cfg.marketplace_country
        info["api_credentials_path"] = str(auth_credentials_path())
        info["api_credentials_present"] = auth_credentials_path().is_file()
        info["library_db_path"] = str(library_db_path())
        n_lib = 0
        if library_db_path().is_file():
            conn = connect(library_db_path())
            init_schema(conn)
            n_lib = db_count(conn)
            conn.close()
        info["library_items"] = n_lib
        return dict(info)

    def post_play(body: dict[str, Any]) -> dict[str, Any]:
        raw = body.get("asin")
        if not isinstance(raw, str):
            raise ValueError("asin must be a string")
        a = validate_asin(raw)
        headless = bool(body.get("headless", False))
        url = webplayer_url(host=cfg.audible_host, asin=a)
        out = launch_web_player(
            binary=cfg.chromium_binary,
            profile_dir=cfg.chromium_profile_dir,
            url=url,
            headless=headless,
            dry_run=False,
        )
        if out.get("via") == "default_browser" and not out.get("opened"):
            raise ValueError(
                "Could not open Chromium or the default browser; set AUDCTL_CHROMIUM_BINARY or open the URL manually."
            )
        proc = out.get("proc")
        pid = getattr(proc, "pid", None) if proc is not None else None
        return {"ok": True, "via": out.get("via"), "pid": pid, "url": url, "opened_default_browser": out.get("opened")}

    def post_sync(_body: dict[str, Any]) -> dict[str, Any]:
        try:
            auth = load_authenticator()
        except FileNotFoundError as exc:
            raise ValueError(str(exc)) from exc
        n = sync_library_to_db(auth=auth, country_code=cfg.marketplace_country)
        return {"ok": True, "indexed": n, "library_db": str(library_db_path())}

    def post_resolve(body: dict[str, Any]) -> dict[str, Any]:
        title = body.get("title")
        asin = body.get("asin")
        if asin and isinstance(asin, str):
            r = resolve_from_asin(title=str(title or asin), asin=asin, host=cfg.audible_host)
        elif title and isinstance(title, str):
            r = resolve_from_library_index(title=title, host=cfg.audible_host)
            if r is None:
                r = resolve_title(
                    title=title,
                    host=cfg.audible_host,
                    allow_search_scrape=cfg.allow_search_scrape,
                )
        else:
            raise ValueError("Provide title (string) and/or asin (string) in JSON body")
        return {"ok": True, "result": r.to_dict()}

    return {
        "GET /": get_index,
        "GET /health": get_health,
        "GET /v1/status": get_status,
        "POST /v1/play": post_play,
        "POST /v1/sync": post_sync,
        "POST /v1/resolve": post_resolve,
    }
