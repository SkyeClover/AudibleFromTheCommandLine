from pathlib import Path

import pytest

from audctl.db import connect, init_schema, upsert_item
from audctl.library_resolve import resolve_from_library_index
from audctl.paths import library_db_path


def test_resolve_prefers_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    dbp = library_db_path()
    conn = connect(dbp)
    init_schema(conn)
    upsert_item(
        conn,
        {
            "asin": "B022222222",
            "title": "SQLite Only Title",
            "authors": ["Auth"],
            "narrators": [],
            "runtime_minutes": None,
            "series_title": None,
            "series_sequence": None,
            "purchase_date": None,
            "raw_json": "{}",
        },
    )
    conn.commit()
    conn.close()

    r = resolve_from_library_index(title="SQLite Only Title", host="www.audible.com")
    assert r is not None
    assert r.asin == "B022222222"
    assert r.resolver == "library_sqlite"
