from pathlib import Path

from audctl.db import best_title_match, connect, init_schema, upsert_item


def test_upsert_and_match(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    conn = connect(db)
    init_schema(conn)
    upsert_item(
        conn,
        {
            "asin": "B011111111",
            "title": "Unique Title Here",
            "authors": ["A"],
            "narrators": [],
            "runtime_minutes": 60,
            "series_title": None,
            "series_sequence": None,
            "purchase_date": None,
            "raw_json": "{}",
        },
    )
    conn.commit()
    row = best_title_match(conn, "Unique Title Here")
    conn.close()
    assert row is not None
    assert row.asin == "B011111111"
    assert row.tracked is True
