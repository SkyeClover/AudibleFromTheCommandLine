"""Launch Chromium pointed at Audible web URLs (DRM stays in the browser)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from audctl.browser_open import open_system_default_browser
from audctl.chromium import pick_chromium_binary


def build_chromium_argv(
    *,
    binary: str,
    profile_dir: Path,
    url: str,
    headless: bool,
    extra_args: list[str] | None = None,
) -> list[str]:
    profile_dir = profile_dir.expanduser()
    argv: list[str] = [binary]
    if headless:
        argv += [
            "--headless=new",
            "--disable-gpu",
            "--window-size=1280,720",
        ]
    argv += [
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--autoplay-policy=no-user-gesture-required",
    ]
    if extra_args:
        argv += list(extra_args)
    argv.append(url)
    return argv


def launch_chromium(
    *,
    binary: str | None,
    profile_dir: Path,
    url: str,
    headless: bool,
    dry_run: bool,
) -> subprocess.Popen[str] | list[str]:
    picked = pick_chromium_binary(binary)
    if not picked:
        raise FileNotFoundError(
            "No Chromium/Chrome binary found. Set AUDCTL_CHROMIUM_BINARY or "
            "chromium_binary in config.toml."
        )
    argv = build_chromium_argv(
        binary=picked,
        profile_dir=profile_dir,
        url=url,
        headless=headless,
    )
    if dry_run:
        return argv
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(
        argv,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        close_fds=os.name != "nt",
        creationflags=creationflags,
        text=True,
    )


def launch_web_player(
    *,
    binary: str | None,
    profile_dir: Path,
    url: str,
    headless: bool,
    dry_run: bool,
) -> dict[str, Any]:
    """
    Open the web player in Chromium when available, otherwise the system default browser.

    Returns a dict with ``via`` of ``chromium`` or ``default_browser``, optional ``argv``,
    ``proc``, ``opened``, and ``url``.
    """
    picked = pick_chromium_binary(binary)
    prefer_default = os.environ.get("AUDCTL_PREFER_DEFAULT_BROWSER", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if picked and not prefer_default:
        out = launch_chromium(
            binary=binary,
            profile_dir=profile_dir,
            url=url,
            headless=headless,
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

    if headless:
        print(
            "audctl: --headless needs Chromium/Chrome/Edge; opening your default browser instead "
            "(visible window).\n",
            file=sys.stderr,
        )
    ok = open_system_default_browser(url)
    if not ok:
        print(f"\naudctl: Could not launch a browser automatically. Open:\n  {url}\n", file=sys.stderr)
    return {"via": "default_browser", "url": url, "opened": ok}
