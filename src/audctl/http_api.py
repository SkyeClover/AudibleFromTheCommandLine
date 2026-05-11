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
from audctl.control import stop_profile_sessions
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
                {"method": "POST", "path": "/v1/play", "description": "Open web player or search (JSON: asin and/or title, headless, offscreen)."},
                {"method": "POST", "path": "/v1/stop", "description": "SIGTERM/SIGKILL Chromium processes using the configured profile."},
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
        headless = bool(body.get("headless", False))
        offscreen = bool(body.get("offscreen", False))
        off_pos = body.get("offscreen_position")
        off_pos_s = off_pos.strip() if isinstance(off_pos, str) else None

        raw_asin = body.get("asin")
        raw_title = body.get("title")
        url: str
        resolved_asin: str | None = None
        resolver: str | None = None

        if isinstance(raw_asin, str) and raw_asin.strip():
            a = validate_asin(raw_asin)
            resolved_asin = a
            url = webplayer_url(host=cfg.audible_host, asin=a)
            resolver = "request_asin"
        elif isinstance(raw_title, str) and raw_title.strip():
            r = resolve_from_library_index(title=raw_title, host=cfg.audible_host)
            if r is None or not r.asin:
                r = resolve_title(
                    title=raw_title,
                    host=cfg.audible_host,
                    allow_search_scrape=cfg.allow_search_scrape,
                )
            resolver = r.resolver
            if r.asin and r.webplayer_url:
                resolved_asin = r.asin
                url = r.webplayer_url
            elif r.search_url:
                url = r.search_url
                if not offscreen and not headless:
                    offscreen = True
            else:
                raise ValueError("Could not resolve title to a URL; try /v1/sync or pass asin.")
        else:
            raise ValueError("JSON body must include asin (string) and/or title (string)")

        out = launch_web_player(
            binary=cfg.chromium_binary,
            profile_dir=cfg.chromium_profile_dir,
            url=url,
            headless=headless,
            dry_run=False,
            offscreen=offscreen and not headless,
            offscreen_position=off_pos_s,
        )
        if out.get("via") == "default_browser" and not out.get("opened"):
            raise ValueError(
                "Could not open Chromium or the default browser; set AUDCTL_CHROMIUM_BINARY or open the URL manually."
            )
        proc = out.get("proc")
        pid = getattr(proc, "pid", None) if proc is not None else None
        return {
            "ok": True,
            "via": out.get("via"),
            "pid": pid,
            "url": url,
            "asin": resolved_asin,
            "resolver": resolver,
            "opened_default_browser": out.get("opened"),
            "headless": headless,
            "offscreen": offscreen and not headless,
        }

    def post_stop(body: dict[str, Any]) -> dict[str, Any]:
        pref = body.get("signal", "term")
        sig = str(pref).strip().lower() if isinstance(pref, str) else "term"
        if sig not in ("term", "kill"):
            sig = "term"
        stopped, log = stop_profile_sessions(cfg.chromium_profile_dir, signal_preference=sig)
        return {"ok": True, "stopped": stopped, "log": log}

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
        "POST /v1/stop": post_stop,
        "POST /v1/sync": post_sync,
        "POST /v1/resolve": post_resolve,
    }
