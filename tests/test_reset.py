from pathlib import Path

import pytest
from typer.testing import CliRunner

from audctl.cli import app


def test_reset_removes_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    st = tmp_path / "state" / "audctl"
    st.mkdir(parents=True)
    cred = st / "audible_credentials.json"
    cred.write_text("{}", encoding="utf-8")
    db = st / "library.db"
    db.write_text("x", encoding="utf-8")

    runner = CliRunner()
    r = runner.invoke(app, ["reset", "--force", "--yes"])
    assert r.exit_code == 0
    assert not cred.is_file()
    assert not db.is_file()


def test_reset_requires_force(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    runner = CliRunner()
    r = runner.invoke(app, ["reset"])
    assert r.exit_code == 2
