import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from audctl.cli import app


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))


def test_resolve_title_json_structure(isolated_env: None) -> None:
    runner = CliRunner()
    r = runner.invoke(app, ["resolve", "--title", "Some Book", "--json"])
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    assert data["title"] == "Some Book"
    assert data["asin"] is None
    assert "confidence" in data
    assert data["resolver"] == "title_fallback"


def test_urls_asin_json(isolated_env: None) -> None:
    runner = CliRunner()
    r = runner.invoke(app, ["urls", "--asin", "B012345678", "--json"])
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    assert data["webplayer_url"].endswith("webplayer?asin=B012345678")
