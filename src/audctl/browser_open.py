"""Open a URL in the OS default browser (cross-platform, Windows-friendly)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import webbrowser

logger = logging.getLogger(__name__)


def open_system_default_browser(url: str) -> bool:
    """
    Try several strategies so playback/login works when ``webbrowser.open`` fails
    (common on Windows depending on association and console context).
    """
    try:
        if webbrowser.open(url, new=1, autoraise=True):
            return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("webbrowser.open failed: %s", exc)

    if sys.platform == "win32":
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return True
        except OSError as exc:
            logger.debug("os.startfile failed: %s", exc)
        try:
            # Classic handler for http/https URLs
            r = subprocess.run(
                ["rundll32", "url.dll,FileProtocolHandler", url],
                shell=False,
                check=False,
                timeout=90,
            )
            if r.returncode == 0:
                return True
        except OSError as exc:
            logger.debug("rundll32 handler failed: %s", exc)
        try:
            # `start` with empty window title argument
            r = subprocess.run(
                ["cmd", "/c", "start", "", url],
                shell=False,
                check=False,
                cwd=os.environ.get("SystemRoot", r"C:\Windows"),
                timeout=90,
            )
            if r.returncode == 0:
                return True
        except OSError as exc:
            logger.debug("cmd start failed: %s", exc)

    elif sys.platform == "darwin":
        try:
            subprocess.run(["open", url], check=False, timeout=90)
            return True
        except OSError as exc:
            logger.debug("open(1) failed: %s", exc)
    else:
        for name in ("xdg-open", "gio"):
            exe = shutil.which(name)
            if exe:
                try:
                    subprocess.run([exe, url], check=False, timeout=90)
                    return True
                except OSError as exc:
                    logger.debug("%s failed: %s", exe, exc)

    return False
