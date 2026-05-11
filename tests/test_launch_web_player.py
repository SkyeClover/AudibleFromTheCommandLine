from pathlib import Path

import pytest

from audctl.play import launch_web_player


def test_launch_web_player_default_browser(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("audctl.play.pick_chromium_binary", lambda *_args, **_kwargs: None)
    opened: dict[str, str] = {}

    def fake_open(url: str) -> bool:
        opened["u"] = url
        return True

    monkeypatch.setattr("audctl.play.open_system_default_browser", fake_open)
    r = launch_web_player(
        binary=None,
        profile_dir=tmp_path,
        url="https://www.audible.com/webplayer?asin=B012345678",
        headless=False,
        dry_run=False,
    )
    assert r["via"] == "default_browser"
    assert r["opened"] is True
    assert "asin=B012345678" in opened["u"]


def test_launch_web_player_dry_run_no_chromium(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("audctl.play.pick_chromium_binary", lambda *_args, **_kwargs: None)
    r = launch_web_player(
        binary=None,
        profile_dir=tmp_path,
        url="https://example.com",
        headless=False,
        dry_run=True,
    )
    assert r["via"] == "default_browser"
    assert r.get("argv") is None
