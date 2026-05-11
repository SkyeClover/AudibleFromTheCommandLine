"""Documented GUI login flow: dedicated Chromium profile, or system default browser."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from audctl.browser_open import open_system_default_browser
from audctl.chromium import pick_chromium_binary
from audctl.play import launch_chromium


def login_landing_url(host: str) -> str:
    h = host.strip().lower()
    if h.startswith("http"):
        return f"{h.split('://',1)[0]}://{h.split('://',1)[1].rstrip('/')}/signin"
    return f"https://{h.rstrip('/')}/signin"


def open_login_window(
    *,
    host: str,
    profile_dir: Path,
    chromium_binary: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    """
    Open Audible sign-in for web cookies.

    Uses Chromium/Chrome/Edge with ``--user-data-dir`` when a binary is found
    on ``PATH`` (or ``AUDCTL_CHROMIUM_BINARY``). Otherwise opens the **system
    default browser** — cookies live in that browser's profile, not audctl's
    isolated Chromium folder, so ``audctl play`` may still need a Chromium
    install for isolated playback unless you point it at the same profile.
    """
    url = login_landing_url(host)
    picked = pick_chromium_binary(chromium_binary)
    prefer_default = os.environ.get("AUDCTL_PREFER_DEFAULT_BROWSER", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    if picked and not prefer_default:
        out = launch_chromium(
            binary=chromium_binary,
            profile_dir=profile_dir,
            url=url,
            headless=False,
            dry_run=dry_run,
        )
        if dry_run and isinstance(out, list):
            return {"via": "chromium", "url": url, "argv": out}
        return {"via": "chromium", "url": url, "proc": out}

    if dry_run:
        return {
            "via": "default_browser",
            "url": url,
            "argv": None,
            "note": "No Chromium/Chrome/Edge on PATH; would open system default browser.",
        }

    print(
        "\naudctl: No dedicated Chromium/Chrome/Edge binary found; opening your **default browser** "
        "for Audible web sign-in.\n"
        "Cookies will be stored in that browser's normal profile (not audctl's isolated folder). "
        "For `audctl play` with a separate profile, install Chrome/Edge/Chromium or set "
        "AUDCTL_CHROMIUM_BINARY.\n",
        file=sys.stderr,
    )
    opened = open_system_default_browser(url)
    if not opened:
        print(
            "\naudctl: Could not open a default browser automatically. "
            f"Open this URL manually:\n  {url}\n",
            file=sys.stderr,
        )
    return {"via": "default_browser", "url": url, "opened": opened}


def session_status(*, host: str, profile_dir: Path, chromium_binary: str | None) -> dict[str, object]:
    profile_dir = profile_dir.expanduser()
    binary = pick_chromium_binary(chromium_binary)
    return {
        "profile_dir": str(profile_dir),
        "profile_exists": profile_dir.is_dir(),
        "chromium_binary_resolved": binary,
        "login_url": login_landing_url(host),
        "web_login_via": "chromium" if binary else "default_browser",
    }
