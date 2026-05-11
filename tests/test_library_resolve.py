import json
from pathlib import Path

import pytest

from audctl.library_resolve import resolve_from_library_index


def test_library_index_exact_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lib = tmp_path / "lib.json"
    lib.write_text(
        json.dumps(
            [
                {"title": "14", "asin": "B012345678"},
                {"title": "Other", "asin": "B099999999"},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AUDCTL_LIBRARY_INDEX", str(lib))
    r = resolve_from_library_index(title="14", host="www.audible.com")
    assert r is not None
    assert r.asin == "B012345678"
    assert r.resolver == "library_index"
