import sys
from pathlib import Path

import pytest

from audctl.config import AudctlConfig, write_config_file


def test_load_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    cfg_dir = tmp_path / "cfg" / "audctl"
    cfg_dir.mkdir(parents=True)
    prof = (tmp_path / "prof").as_posix()
    (cfg_dir / "config.toml").write_text(
        'audible_host = "www.audible.co.uk"\n'
        f'chromium_profile_dir = "{prof}"\n'
        'marketplace_country = "uk"\n'
        "allow_search_scrape = true\n",
        encoding="utf-8",
    )
    cfg = AudctlConfig.load()
    assert cfg.audible_host == "www.audible.co.uk"
    assert cfg.chromium_profile_dir == tmp_path / "prof"
    assert cfg.marketplace_country == "uk"
    assert cfg.allow_search_scrape is True


def test_env_overrides_scrape_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("AUDCTL_ALLOW_SEARCH_SCRAPE", "0")
    cfg_dir = tmp_path / "cfg" / "audctl"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.toml").write_text("allow_search_scrape = true\n", encoding="utf-8")
    cfg = AudctlConfig.load()
    assert cfg.allow_search_scrape is False


def test_write_config_file_restricts(tmp_path: Path) -> None:
    p = tmp_path / "c.toml"
    write_config_file(p, {"audible_host": "www.audible.com"})
    assert p.is_file()
    if sys.platform != "win32":
        mode = oct(p.stat().st_mode)[-3:]
        assert mode == "600"
