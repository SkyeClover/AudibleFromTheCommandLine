"""XDG-oriented configuration and filesystem layout."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomllib

_ENV_PREFIX = "AUDCTL_"


def _xdg_config_home() -> Path:
    raw = os.environ.get("XDG_CONFIG_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".config"


def xdg_state_home() -> Path:
    raw = os.environ.get("XDG_STATE_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".local" / "state"


def _xdg_cache_home() -> Path:
    raw = os.environ.get("XDG_CACHE_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".cache"


def default_chromium_profile_dir() -> Path:
    """Prefer explicit env, then snap-friendly Chromium path when on Ubuntu snap."""
    override = os.environ.get(f"{_ENV_PREFIX}CHROMIUM_PROFILE_DIR")
    if override:
        return Path(override).expanduser()
    snap_common = os.environ.get("SNAP_USER_COMMON")
    if snap_common:
        return Path(snap_common) / "audctl-chromium-profile"
    return xdg_state_home() / "audctl" / "chromium-profile"


def default_audible_host() -> str:
    return os.environ.get(f"{_ENV_PREFIX}AUDIBLE_HOST", "www.audible.com").strip()


def default_chromium_binary() -> str | None:
    return os.environ.get(f"{_ENV_PREFIX}CHROMIUM_BINARY")


def default_marketplace_country() -> str:
    raw = os.environ.get(f"{_ENV_PREFIX}MARKETPLACE", "us").strip().lower()
    return raw or "us"


@dataclass
class AudctlConfig:
    """Resolved configuration (file + environment overrides)."""

    audible_host: str = field(default_factory=default_audible_host)
    marketplace_country: str = field(default_factory=default_marketplace_country)
    chromium_profile_dir: Path = field(default_factory=default_chromium_profile_dir)
    chromium_binary: str | None = field(default_factory=default_chromium_binary)
    allow_search_scrape: bool = field(
        default_factory=lambda: os.environ.get(f"{_ENV_PREFIX}ALLOW_SEARCH_SCRAPE", "")
        .strip()
        .lower()
        in {"1", "true", "yes"},
    )

    @property
    def config_dir(self) -> Path:
        return _xdg_config_home() / "audctl"

    @property
    def config_path(self) -> Path:
        return self.config_dir / "config.toml"

    @property
    def state_dir(self) -> Path:
        return xdg_state_home() / "audctl"

    def ensure_private_dirs(self) -> None:
        """Create state/config dirs and tighten permissions where we store sessions."""
        for base in (self.config_dir, self.state_dir, self.chromium_profile_dir.parent):
            base.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(base, 0o700)
            except OSError:
                pass
        self.chromium_profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.chromium_profile_dir, 0o700)
        except OSError:
            pass

    @classmethod
    def load(cls) -> AudctlConfig:
        cfg = cls()
        path = cfg.config_path
        if not path.is_file():
            return cfg
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return cfg
        audible_host = data.get("audible_host")
        if isinstance(audible_host, str) and audible_host.strip():
            cfg.audible_host = audible_host.strip()
        profile = data.get("chromium_profile_dir")
        if isinstance(profile, str) and profile.strip():
            cfg.chromium_profile_dir = Path(profile).expanduser()
        binary = data.get("chromium_binary")
        if isinstance(binary, str) and binary.strip():
            cfg.chromium_binary = binary.strip()
        mc = data.get("marketplace_country")
        if isinstance(mc, str) and mc.strip():
            cfg.marketplace_country = mc.strip().lower()
        allow = data.get("allow_search_scrape")
        if isinstance(allow, bool):
            cfg.allow_search_scrape = allow
        env_scrape = os.environ.get(f"{_ENV_PREFIX}ALLOW_SEARCH_SCRAPE")
        if env_scrape is not None and str(env_scrape).strip() != "":
            cfg.allow_search_scrape = str(env_scrape).strip().lower() in {"1", "true", "yes"}
        env_mp = os.environ.get(f"{_ENV_PREFIX}MARKETPLACE")
        if env_mp is not None and str(env_mp).strip() != "":
            cfg.marketplace_country = str(env_mp).strip().lower()
        return cfg


def restrict_file_permissions(path: Path) -> None:
    """Best-effort chmod 600 for token/session-like files."""
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def write_config_file(path: Path, payload: dict[str, Any]) -> None:
    """Write TOML config and restrict permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    lines = []
    for key, value in payload.items():
        if isinstance(value, str):
            lines.append(f'{key} = {repr(value)}')
        elif isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, Path):
            lines.append(f'{key} = {repr(str(value))}')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    restrict_file_permissions(path)
