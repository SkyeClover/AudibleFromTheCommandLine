"""
First-time login using the **unofficial** `audible` Python package (internal API).

This is not from Amazon; tokens are stored locally for library sync only.
"""

from __future__ import annotations

import getpass
from pathlib import Path
from typing import Any, Callable

import typer

from audctl.amazon_login import AudctlLoginError, apply_device_login_patch, restore_device_login_patch
from audctl.config import restrict_file_permissions
from audctl.paths import auth_credentials_path, state_dir


def require_audible_module() -> Any:
    try:
        import audible as audible_mod  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "The `audible` package is required for API login and library sync. "
            "Install with: pip install audctl"
        ) from exc
    return audible_mod


def _otp_callback() -> str:
    typer.echo("Amazon asked for an authenticator-app code (TOTP / 2FA).")
    return typer.prompt("Enter the code", type=str).strip()


def _cvf_callback() -> str:
    """Used when the interactive CVF menu chose 'enter code' (legacy hook)."""
    return typer.prompt("Verification code (SMS / email)", type=str).strip()


def _approval_callback() -> None:
    typer.echo("Amazon is waiting for you to approve the sign-in (e.g. mobile notification).")
    typer.prompt("Press Enter after you approve", default="")


def _captcha_callback(url: str) -> str:
    typer.echo(f"Amazon requires a CAPTCHA. Open this URL in a browser if needed:\n  {url}")
    return typer.prompt("CAPTCHA text (lowercase)", type=str).strip().lower()


def run_setup_wizard(
    *,
    country_code: str,
    with_username: bool = False,
    skip_browser_login_prompt: bool = False,
    open_browser_login: Callable[[], object] | None = None,
) -> Path:
    """
    Prompt for email/password, handle OTP/CVF via Typer, save encrypted credentials.

    If `open_browser_login` is provided and user accepts, opens Chromium for web session.
    """
    audible = require_audible_module()
    typer.echo(
        "\n".join(
            [
                "",
                "── First-time API login (unofficial `audible` library) ──",
                "This stores encrypted tokens under your XDG state directory.",
                "Amazon may show this registration as a new device in your account.",
                "",
            ]
        )
    )
    email = typer.prompt("Audible / Amazon email")
    password = getpass.getpass("Password (hidden): ")

    path = auth_credentials_path()
    state_dir().mkdir(parents=True, exist_ok=True)

    apply_device_login_patch()
    try:
        auth = audible.Authenticator.from_login(
            username=email,
            password=password,
            locale=country_code.lower(),
            with_username=with_username,
            captcha_callback=_captcha_callback,
            otp_callback=_otp_callback,
            cvf_callback=_cvf_callback,
            approval_callback=_approval_callback,
        )
    except AudctlLoginError as exc:
        typer.echo(f"\n{exc}\n", err=True)
        raise typer.Exit(3) from exc
    except Exception as exc:
        typer.echo(
            "\nLogin failed (unexpected error). Check email/password, CAPS LOCK, "
            "marketplace (-m), and Amazon/Audible account region.\n",
            err=True,
        )
        typer.echo(f"Detail: {exc!r}\n", err=True)
        raise typer.Exit(3) from exc
    finally:
        restore_device_login_patch()

    auth.to_file(path)
    restrict_file_permissions(path)
    typer.echo(f"\nSaved API credentials to {path} (mode 600 on POSIX).\n")

    if not skip_browser_login_prompt and open_browser_login is not None:
        if typer.confirm(
            "Open a browser for Audible **web** login (Chromium/Chrome/Edge if found, "
            "otherwise your system default browser)? "
            "Recommended so the web player has cookies for playback.",
            default=True,
        ):
            open_browser_login()

    return path


def load_authenticator() -> Any:
    audible = require_audible_module()
    path = auth_credentials_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"No credentials at {path}. Run `audctl setup` or `audctl` for first-time setup."
        )
    return audible.Authenticator.from_file(path)
