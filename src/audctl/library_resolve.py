"""Optional local library hints (unofficial; user-maintained export)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from audctl.asin import is_valid_asin, normalize_asin
from audctl.db import best_title_match, connect, init_schema
from audctl.paths import library_db_path
from audctl.resolve import ResolveResult
from audctl.urls import search_url, store_url, webplayer_url


def library_index_path() -> Path:
    import os

    raw = os.environ.get("AUDCTL_LIBRARY_INDEX")
    if raw:
        return Path(raw).expanduser()
    from audctl.config import xdg_state_home

    return xdg_state_home() / "audctl" / "library_index.json"


def _resolve_from_sqlite(*, title: str, host: str) -> ResolveResult | None:
    dbp = library_db_path()
    if not dbp.is_file():
        return None
    conn = connect(dbp)
    init_schema(conn)
    row = best_title_match(conn, title)
    conn.close()
    if row is None:
        return None
    n = normalize_asin(row.asin)
    if not is_valid_asin(n):
        return None
    extra: list[str] = []
    if row.authors:
        extra.append(f"Authors: {', '.join(row.authors)}")
    if row.narrators:
        extra.append(f"Narrators: {', '.join(row.narrators)}")
    if row.series_title:
        extra.append(f"Series: {row.series_title}")
    notes = ["Matched local library index from `audctl sync` (unofficial API)."]
    if extra:
        notes.append("; ".join(extra))
    return ResolveResult(
        title=row.title,
        asin=n,
        confidence=0.9,
        store_url=store_url(host=host, asin=n),
        webplayer_url=webplayer_url(host=host, asin=n),
        search_url=search_url(host=host, query=title),
        resolver="library_sqlite",
        notes=notes,
    )


def resolve_from_library_index(*, title: str, host: str) -> ResolveResult | None:
    """
    Prefer SQLite (`audctl sync`), then optional legacy library_index.json.
    """
    hit = _resolve_from_sqlite(title=title, host=host)
    if hit is not None:
        return hit
    path = library_index_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, list):
        return None
    needle = title.strip().lower()
    if not needle:
        return None
    best: dict[str, Any] | None = None
    for row in data:
        if not isinstance(row, dict):
            continue
        t = row.get("title")
        a = row.get("asin")
        if not isinstance(t, str) or not isinstance(a, str):
            continue
        if t.strip().lower() == needle:
            best = row
            break
        if needle in t.lower() and best is None:
            best = row
    if best is None:
        return None
    asin_raw = str(best.get("asin", ""))
    n = normalize_asin(asin_raw)
    if not is_valid_asin(n):
        return None
    t2 = str(best.get("title", title))
    return ResolveResult(
        title=t2,
        asin=n,
        confidence=0.75,
        store_url=store_url(host=host, asin=n),
        webplayer_url=webplayer_url(host=host, asin=n),
        search_url=search_url(host=host, query=title),
        resolver="library_index",
        notes=[
            "Matched audctl library_index.json (user-maintained). "
            "This file is not from Audible; verify ASINs against your account.",
        ],
    )


def library_stub_message() -> str:
    return (
        "Library listings use the unofficial PyPI `audible` package (internal API). "
        "Run `audctl sync` after `audctl setup`. Subject to Amazon ToS; may break if Amazon changes APIs."
    )
