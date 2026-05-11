"""Default entry when no subcommand: first-time API login + optional sync + TUI."""

from __future__ import annotations

import typer

from audctl.auth_setup import load_authenticator, run_setup_wizard
from audctl.config import AudctlConfig
from audctl.library_sync import sync_library_to_db
from audctl.paths import auth_credentials_path
from audctl.session import open_login_window
from audctl.tui_app import run_library_tui


def default_entry(cfg: AudctlConfig | None = None) -> None:
    if cfg is None:
        cfg = AudctlConfig.load()
    cfg.ensure_private_dirs()

    if not auth_credentials_path().is_file():
        typer.echo(
            "\n".join(
                [
                    "",
                    "No API credentials yet — first-time setup.",
                    "You may be prompted for email, password, authenticator code, or SMS/email codes.",
                    "",
                ]
            )
        )
        run_setup_wizard(
            country_code=cfg.marketplace_country,
            open_browser_login=lambda: open_login_window(
                host=cfg.audible_host,
                profile_dir=cfg.chromium_profile_dir,
                chromium_binary=cfg.chromium_binary,
                dry_run=False,
            ),
        )
        try:
            auth = load_authenticator()
            n = sync_library_to_db(auth=auth, country_code=cfg.marketplace_country)
            typer.echo(f"\nIndexed {n} title(s) from your library.\n")
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"Library sync failed (you can retry with `audctl sync`): {exc}\n", err=True)

    run_library_tui(cfg)
