"""Typer CLI entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import typer

from audctl import __version__
from audctl.asin import validate_asin
from audctl.auth_setup import load_authenticator, run_setup_wizard
from audctl.chromium import pick_chromium_binary
from audctl.config import AudctlConfig, restrict_file_permissions, write_config_file
from audctl.control import pause_resume_mpris_hint, stop_profile_sessions
from audctl.country_host import audible_host_for_country
from audctl.db import connect, count as db_count, init_schema
from audctl.library_resolve import library_index_path, library_stub_message, resolve_from_library_index
from audctl.library_sync import sync_library_to_db
from audctl.paths import auth_credentials_path, library_db_path
from audctl.play import build_chromium_argv, launch_web_player
from audctl.resolve import ResolveResult, dumps_json, resolve_from_asin, resolve_title
from audctl.http_api import build_routes
from audctl.serve import build_server
from audctl.session import open_login_window, session_status
from audctl.tui_app import run_library_tui
from audctl.urls import search_url, store_url, webplayer_url

app = typer.Typer(
    invoke_without_command=True,
    no_args_is_help=False,
    help="Audible from the terminal: API library index + web player launch (unofficial; not from Amazon).",
)


def _version_flag(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit(0)


@app.callback()
def _bootstrap(
    ctx: typer.Context,
    _version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_flag,
        is_eager=True,
        help="Print audctl version and exit.",
    ),
) -> None:
    del _version
    if ctx.invoked_subcommand is None:
        from audctl.bootstrap import default_entry

        default_entry()
        raise typer.Exit(0)


def _cfg() -> AudctlConfig:
    cfg = AudctlConfig.load()
    cfg.ensure_private_dirs()
    return cfg


def _emit(data: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        sys.stdout.write(dumps_json(data))
    else:
        for key, value in data.items():
            if isinstance(value, list):
                typer.echo(f"{key}:")
                for line in value:
                    typer.echo(f"  - {line}")
            elif value is None:
                typer.echo(f"{key}: ")
            else:
                typer.echo(f"{key}: {value}")


@app.command("setup")
def setup_cmd(
    marketplace: str = typer.Option(
        "us",
        "--marketplace",
        "-m",
        help="Marketplace country code (us, uk, de, fr, ca, …) for the unofficial API.",
    ),
    with_username: bool = typer.Option(
        False,
        "--with-username",
        help="Use legacy Audible username login (supported marketplaces only).",
    ),
    skip_browser: bool = typer.Option(
        False,
        "--skip-browser-login",
        help="Skip the optional Chromium step for web cookies.",
    ),
) -> None:
    """First-time API login (email/password; OTP / SMS / CAPTCHA as Amazon requires)."""
    cfg = _cfg()
    mc = (marketplace or cfg.marketplace_country).strip().lower()
    run_setup_wizard(
        country_code=mc,
        with_username=with_username,
        skip_browser_login_prompt=skip_browser,
        open_browser_login=None
        if skip_browser
        else (
            lambda: open_login_window(
                host=cfg.audible_host,
                profile_dir=cfg.chromium_profile_dir,
                chromium_binary=cfg.chromium_binary,
                dry_run=False,
            )
        ),
    )


@app.command("sync")
def sync_cmd() -> None:
    """Download your Audible library metadata into the local SQLite index."""
    cfg = _cfg()
    try:
        auth = load_authenticator()
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    n = sync_library_to_db(auth=auth, country_code=cfg.marketplace_country)
    typer.echo(f"Indexed {n} item(s) → {library_db_path()}")


@app.command("tui")
def tui_cmd() -> None:
    """Open the terminal UI (same as running `audctl` with no arguments)."""
    run_library_tui(_cfg())


@app.command("login")
def login_cmd(
    dry_run: bool = typer.Option(False, "--dry-run", help="Print Chromium argv only."),
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable output."),
) -> None:
    """Web sign-in for playback cookies (Chromium/Chrome/Edge when available, else default browser). Use `audctl setup` for API + library sync."""
    cfg = _cfg()
    result = open_login_window(
        host=cfg.audible_host,
        profile_dir=cfg.chromium_profile_dir,
        chromium_binary=cfg.chromium_binary,
        dry_run=dry_run,
    )
    st = session_status(host=cfg.audible_host, profile_dir=cfg.chromium_profile_dir, chromium_binary=cfg.chromium_binary)
    via = str(result.get("via", "chromium"))
    if dry_run:
        if via == "chromium":
            payload = {"argv": result.get("argv"), "login_url": st["login_url"], "via": via}
        else:
            payload = {
                "login_url": result.get("url", st["login_url"]),
                "via": via,
                "note": result.get("note"),
            }
        _emit(payload, as_json=json_out)
        raise typer.Exit(0)
    if json_out:
        payload: dict[str, Any] = {
            "launched": True,
            "profile_dir": str(cfg.chromium_profile_dir),
            "login_url": st["login_url"],
            "via": via,
        }
        proc = result.get("proc")
        if via == "chromium" and proc is not None:
            payload["pid"] = getattr(proc, "pid", None)
        if via == "default_browser":
            payload["opened_default_browser"] = bool(result.get("opened"))
        _emit(payload, as_json=True)
    else:
        if via == "chromium":
            proc = result.get("proc")
            pid = getattr(proc, "pid", "?") if proc is not None else "?"
            typer.echo(
                f"Launched Chromium (pid {pid}) for interactive login. Complete sign-in, then use "
                "`audctl status` before `audctl play`."
            )
        else:
            typer.echo(
                "Opened your default web browser for Audible sign-in. "
                "When finished, use `audctl status`; for isolated `audctl play`, install Chrome/Edge/Chromium."
            )


@app.command("logout")
def logout_cmd(
    purge_profile: bool = typer.Option(
        False,
        "--purge-profile",
        help="Delete the audctl Chromium profile directory (local session cookies).",
    ),
    force: bool = typer.Option(False, "--force", help="Required with --purge-profile."),
) -> None:
    """
    Logout guidance: Audible sessions live in the browser profile.

    Without --purge-profile, this prints steps only. Purging deletes local cookies for this profile.
    """
    cfg = _cfg()
    if purge_profile:
        if not force:
            typer.echo("Refusing to delete profile without --force. Re-run with --force.", err=True)
            raise typer.Exit(2)
        import shutil

        p = cfg.chromium_profile_dir
        if p.is_dir():
            shutil.rmtree(p)
            typer.echo(f"Removed profile directory: {p}")
        else:
            typer.echo(f"No profile directory at {p}")
        raise typer.Exit(0)
    typer.echo(
        "To end the Audible web session for this tool, sign out inside the browser window, "
        "or run `audctl logout --purge-profile --force` to delete the dedicated profile "
        f"at {cfg.chromium_profile_dir}."
    )


@app.command("reset")
def reset_cmd(
    force: bool = typer.Option(
        False,
        "--force",
        help="Required. Deletes local API credentials, library index, and optional legacy JSON.",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt (for scripts)."),
    purge_browser_profile: bool = typer.Option(
        False,
        "--purge-browser-profile",
        help="Also delete the audctl Chromium profile directory (same as logout --purge-profile).",
    ),
) -> None:
    """
    Remove locally stored login and library data so you can run first-time setup again.

    Does **not** change Amazon account passwords or deregister the virtual device on Amazon’s side;
    you can manage devices from your Amazon account if needed.
    """
    if not force:
        typer.echo(
            "Refusing: `audctl reset` is destructive. Re-run with --force (and usually --yes in scripts).",
            err=True,
        )
        raise typer.Exit(2)
    if not yes:
        if not typer.confirm(
            "Delete saved API credentials, library.db, and legacy library_index.json (if present)?",
            default=False,
        ):
            raise typer.Exit(1)

    import shutil

    removed: list[str] = []
    cred = auth_credentials_path()
    if cred.is_file():
        cred.unlink()
        removed.append(str(cred))
    lib = library_db_path()
    if lib.is_file():
        lib.unlink()
        removed.append(str(lib))
    legacy = library_index_path()
    if legacy.is_file():
        legacy.unlink()
        removed.append(str(legacy))

    cfg = _cfg()
    if purge_browser_profile:
        p = cfg.chromium_profile_dir
        if p.is_dir():
            shutil.rmtree(p)
            removed.append(str(p))
        else:
            typer.echo(f"(No browser profile directory at {p})")

    if removed:
        typer.echo("Removed:")
        for line in removed:
            typer.echo(f"  {line}")
    else:
        typer.echo("Nothing was on disk to remove (paths were already missing).")
    typer.echo("\nRun `audctl` or `audctl setup` to go through login and indexing again.\n")


@app.command("status")
def status_cmd(json_out: bool = typer.Option(False, "--json")) -> None:
    """Show resolved Chromium profile path and whether the binary exists."""
    cfg = _cfg()
    info = session_status(host=cfg.audible_host, profile_dir=cfg.chromium_profile_dir, chromium_binary=cfg.chromium_binary)
    info["version"] = __version__
    info["allow_search_scrape"] = cfg.allow_search_scrape
    info["library_stub"] = library_stub_message()
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
    _emit({k: v for k, v in info.items()}, as_json=json_out)


@app.command("resolve")
def resolve_cmd(
    title: str | None = typer.Option(None, "--title", help="Free-text title; ASIN may be unknown."),
    asin: str | None = typer.Option(None, "--asin", help="Known ASIN (10 characters)."),
    json_out: bool = typer.Option(False, "--json"),
    url_only: bool = typer.Option(False, "--url-only", help="Print a single URL line (webplayer if known else search)."),
) -> None:
    """Resolve a title to structured URLs and optional ASIN hints."""
    cfg = _cfg()
    result: ResolveResult | None = None
    if asin:
        result = resolve_from_asin(title=title or asin, asin=asin, host=cfg.audible_host)
    elif title:
        result = resolve_from_library_index(title=title, host=cfg.audible_host)
        if result is None:
            result = resolve_title(
                title=title,
                host=cfg.audible_host,
                allow_search_scrape=cfg.allow_search_scrape,
            )
    else:
        typer.echo("Provide --title and/or --asin.", err=True)
        raise typer.Exit(2)

    if url_only:
        url = result.webplayer_url or result.search_url
        if not url:
            typer.echo("", err=True)
            raise typer.Exit(3)
        typer.echo(url)
        raise typer.Exit(0)

    if json_out:
        sys.stdout.write(dumps_json(result.to_dict()))
        raise typer.Exit(0)

    typer.echo(f"title: {result.title}")
    typer.echo(f"asin: {result.asin}")
    typer.echo(f"confidence: {result.confidence}")
    typer.echo(f"resolver: {result.resolver}")
    if result.webplayer_url:
        typer.echo(f"webplayer_url: {result.webplayer_url}")
    if result.store_url:
        typer.echo(f"store_url: {result.store_url}")
    if result.search_url:
        typer.echo(f"search_url: {result.search_url}")
    if result.notes:
        for n in result.notes:
            typer.echo(f"note: {n}")


@app.command("play")
def play_cmd(
    title: str | None = typer.Option(None, "--title"),
    asin: str | None = typer.Option(None, "--asin"),
    headless: bool = typer.Option(False, "--headless", help="Use Chromium headless mode (playback depends on OS/audio)."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    json_out: bool = typer.Option(False, "--json"),
    url_only: bool = typer.Option(False, "--url-only", help="Print webplayer URL and exit (no browser)."),
) -> None:
    """Open the Audible web player for a title or ASIN (Chromium when available, else default browser)."""
    cfg = _cfg()
    if asin:
        a = validate_asin(asin)
        url = webplayer_url(host=cfg.audible_host, asin=a)
    elif title:
        r = resolve_from_library_index(title=title, host=cfg.audible_host)
        if r is None or not r.asin:
            r = resolve_title(title=title, host=cfg.audible_host, allow_search_scrape=cfg.allow_search_scrape)
        if not r.asin:
            typer.echo(
                "Could not determine an ASIN. Run `audctl sync` after setup, use --asin, "
                "or enable AUDCTL_ALLOW_SEARCH_SCRAPE for fragile HTML guessing.",
                err=True,
            )
            raise typer.Exit(4)
        url = r.webplayer_url or webplayer_url(host=cfg.audible_host, asin=r.asin)
    else:
        typer.echo("Provide --asin or --title.", err=True)
        raise typer.Exit(2)

    if url_only:
        typer.echo(url)
        raise typer.Exit(0)

    out = launch_web_player(
        binary=cfg.chromium_binary,
        profile_dir=cfg.chromium_profile_dir,
        url=url,
        headless=headless,
        dry_run=dry_run,
    )
    if dry_run:
        _emit({"url": url, **out}, as_json=json_out)
        raise typer.Exit(0)
    via = str(out.get("via", "chromium"))
    if via == "default_browser" and not out.get("opened"):
        typer.echo(
            "Could not open a browser automatically. Open the URL above manually, "
            "or set AUDCTL_CHROMIUM_BINARY to Chrome/Edge/Chromium.",
            err=True,
        )
        raise typer.Exit(7)
    if json_out:
        binary = pick_chromium_binary(cfg.chromium_binary)
        argv: list[str] | None = None
        if binary:
            argv = build_chromium_argv(
                binary=binary,
                profile_dir=cfg.chromium_profile_dir,
                url=url,
                headless=headless,
            )
        payload: dict[str, Any] = {"launched": True, "url": url, "via": via, "argv": argv}
        proc = out.get("proc")
        if via == "chromium" and proc is not None:
            payload["pid"] = getattr(proc, "pid", None)
        if via == "default_browser":
            payload["opened_default_browser"] = bool(out.get("opened"))
        _emit(payload, as_json=True)
    else:
        if via == "chromium":
            proc = out.get("proc")
            pid = getattr(proc, "pid", "?") if proc is not None else "?"
            typer.echo(f"Launched Chromium (pid {pid}) → {url}")
        else:
            typer.echo(f"Opened default browser → {url}")


@app.command("stop")
def stop_cmd(
    json_out: bool = typer.Option(False, "--json"),
    kill: bool = typer.Option(False, "--kill", help="Send SIGKILL instead of SIGTERM (Linux)."),
) -> None:
    """Stop Chromium instances that use the configured audctl profile (see README)."""
    cfg = _cfg()
    n, log = stop_profile_sessions(cfg.chromium_profile_dir, signal_preference="kill" if kill else "term")
    payload: dict[str, Any] = {"stopped_processes": n, "log": log}
    _emit(payload, as_json=json_out)
    if n == 0:
        raise typer.Exit(5)


@app.command("pause")
def pause_cmd(json_out: bool = typer.Option(False, "--json")) -> None:
    """Not implemented: documents MPRIS / playerctl alternative."""
    msg = pause_resume_mpris_hint()
    if json_out:
        _emit({"supported": False, "hint": msg}, as_json=True)
    else:
        typer.echo(msg)
    raise typer.Exit(6)


@app.command("resume")
def resume_cmd(json_out: bool = typer.Option(False, "--json")) -> None:
    """Same as pause: use desktop MPRIS tools where available."""
    pause_cmd(json_out=json_out)


@app.command("init-config")
def init_config_cmd(
    audible_host: str | None = typer.Option(None, "--audible-host"),
    marketplace: str | None = typer.Option(
        None,
        "--marketplace",
        "-m",
        help="Set marketplace and default www.audible.* host together.",
    ),
    profile_dir: Path | None = typer.Option(None, "--chromium-profile-dir", exists=False),
) -> None:
    """Write $XDG_CONFIG_HOME/audctl/config.toml with chmod 600."""
    cfg = _cfg()
    payload: dict[str, Any] = {}
    if marketplace:
        mc = marketplace.strip().lower()
        payload["marketplace_country"] = mc
        payload["audible_host"] = audible_host or audible_host_for_country(mc)
    elif audible_host:
        payload["audible_host"] = audible_host
    else:
        payload["audible_host"] = cfg.audible_host
        payload["marketplace_country"] = cfg.marketplace_country
    if profile_dir is not None:
        payload["chromium_profile_dir"] = profile_dir
    elif cfg.chromium_profile_dir:
        payload["chromium_profile_dir"] = cfg.chromium_profile_dir
    write_config_file(cfg.config_path, payload)
    restrict_file_permissions(cfg.config_path)
    typer.echo(f"Wrote {cfg.config_path}")


@app.command("urls")
def urls_cmd(
    asin: str = typer.Option(..., "--asin"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Print store / webplayer / search helper URLs for an ASIN."""
    cfg = _cfg()
    a = validate_asin(asin)
    data = {
        "asin": a,
        "store_url": store_url(host=cfg.audible_host, asin=a),
        "webplayer_url": webplayer_url(host=cfg.audible_host, asin=a),
        "search_url": search_url(host=cfg.audible_host, query=a),
    }
    _emit(data, as_json=json_out)


@app.command("serve")
def serve_cmd(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address (use 127.0.0.1 only unless proxied with auth)."),
    port: int = typer.Option(8765, "--port"),
) -> None:
    """
    Local JSON HTTP API on http://HOST:PORT (default 127.0.0.1:8765).

    Run ``curl -s http://127.0.0.1:8765/`` for a list of endpoints. No auth/TLS by default—
    do not expose to the internet without a reverse proxy and authentication.
    """
    cfg = _cfg()
    routes = build_routes(cfg)
    httpd = build_server(host, port, routes=routes)
    typer.echo(f"audctl serve listening on http://{host}:{port} (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        typer.echo("Shutting down.")
        httpd.shutdown()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
