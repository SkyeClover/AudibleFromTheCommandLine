"""SQLite cache of library titles (from unofficial API sync)."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS library_items (
            asin TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            authors_json TEXT,
            narrators_json TEXT,
            runtime_minutes INTEGER,
            series_title TEXT,
            series_sequence TEXT,
            purchase_date TEXT,
            tracked INTEGER NOT NULL DEFAULT 1,
            raw_json TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_library_title ON library_items(title);
        CREATE INDEX IF NOT EXISTS idx_library_tracked ON library_items(tracked);
        """
    )
    conn.commit()


@dataclass
class LibraryRow:
    asin: str
    title: str
    authors: list[str]
    narrators: list[str]
    runtime_minutes: int | None
    series_title: str | None
    series_sequence: str | None
    purchase_date: str | None
    tracked: bool


def _loads_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(x) for x in data]


def upsert_item(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn.execute(
        """
        INSERT INTO library_items (
            asin, title, authors_json, narrators_json, runtime_minutes,
            series_title, series_sequence, purchase_date, tracked, raw_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(asin) DO UPDATE SET
            title = excluded.title,
            authors_json = excluded.authors_json,
            narrators_json = excluded.narrators_json,
            runtime_minutes = excluded.runtime_minutes,
            series_title = excluded.series_title,
            series_sequence = excluded.series_sequence,
            purchase_date = excluded.purchase_date,
            raw_json = excluded.raw_json,
            updated_at = excluded.updated_at
        """,
        (
            row["asin"],
            row["title"],
            json.dumps(row.get("authors") or []),
            json.dumps(row.get("narrators") or []),
            row.get("runtime_minutes"),
            row.get("series_title"),
            row.get("series_sequence"),
            row.get("purchase_date"),
            row.get("raw_json"),
            now,
        ),
    )


def set_tracked(conn: sqlite3.Connection, asin: str, tracked: bool) -> None:
    conn.execute(
        "UPDATE library_items SET tracked = ? WHERE asin = ?",
        (1 if tracked else 0, asin),
    )
    conn.commit()


def iter_rows(
    conn: sqlite3.Connection,
    *,
    tracked_only: bool = False,
    query: str | None = None,
) -> Iterator[LibraryRow]:
    sql = "SELECT * FROM library_items WHERE 1=1"
    params: list[Any] = []
    if tracked_only:
        sql += " AND tracked = 1"
    if query:
        q = f"%{query.strip().lower()}%"
        sql += " AND lower(title) LIKE ?"
        params.append(q)
    sql += " ORDER BY title COLLATE NOCASE"
    for r in conn.execute(sql, params):
        tracked = bool(r["tracked"])
        yield LibraryRow(
            asin=str(r["asin"]),
            title=str(r["title"]),
            authors=_loads_list(r["authors_json"]),
            narrators=_loads_list(r["narrators_json"]),
            runtime_minutes=r["runtime_minutes"],
            series_title=r["series_title"],
            series_sequence=r["series_sequence"],
            purchase_date=r["purchase_date"],
            tracked=tracked,
        )


def best_title_match(conn: sqlite3.Connection, title: str) -> LibraryRow | None:
    needle = title.strip().lower()
    if not needle:
        return None
    best: LibraryRow | None = None
    for row in iter_rows(conn, tracked_only=True):
        t = row.title.lower()
        if t == needle:
            return row
        if needle in t and best is None:
            best = row
    return best


def count(conn: sqlite3.Connection) -> int:
    cur = conn.execute("SELECT COUNT(*) FROM library_items")
    return int(cur.fetchone()[0])
