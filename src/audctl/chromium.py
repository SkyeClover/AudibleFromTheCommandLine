"""Locate Chromium / Chrome for launch and control."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def candidate_binaries(cfg_binary: str | None) -> list[str]:
    if cfg_binary:
        return [cfg_binary]
    env = os.environ.get("AUDCTL_CHROMIUM_BINARY")
    if env:
        return [env.strip()]
    names = [
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "chrome",
        "msedge",
    ]
    found: list[str] = []
    for name in names:
        path = shutil.which(name)
        if path:
            found.append(path)
    return found


def pick_chromium_binary(cfg_binary: str | None) -> str | None:
    for c in candidate_binaries(cfg_binary):
        if Path(c).is_file():
            return c
    return None
