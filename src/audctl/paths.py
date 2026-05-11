"""Well-known paths under XDG state (credentials + SQLite)."""

from __future__ import annotations

from pathlib import Path

from audctl.config import xdg_state_home


def state_dir() -> Path:
    return xdg_state_home() / "audctl"


def auth_credentials_path() -> Path:
    """Encrypted auth blob written by the unofficial `audible` library."""
    return state_dir() / "audible_credentials.json"


def library_db_path() -> Path:
    return state_dir() / "library.db"
