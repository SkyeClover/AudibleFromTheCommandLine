"""Pull library pages from Audible internal API into SQLite."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from audctl.db import connect, init_schema, upsert_item
from audctl.item_parse import parse_library_item
from audctl.paths import library_db_path


def sync_library_to_db(
    *,
    auth: Any,
    country_code: str,
    db_path: Path | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> int:
    """Return number of items upserted."""
    import audible  # type: ignore[import-untyped]

    path = library_db_path() if db_path is None else Path(db_path)
    conn = connect(path)
    init_schema(conn)
    total = 0
    page = 1
    page_size = 1000
    with audible.Client(auth=auth, country_code=country_code.lower()) as client:
        while True:
            data = client.get(
                "1.0/library",
                num_results=page_size,
                page=page,
                response_groups="contributors, product_desc, product_attrs, series, media, order_details",
                sort_by="-PurchaseDate",
            )
            if not isinstance(data, dict):
                break
            items = data.get("items")
            if not isinstance(items, list) or not items:
                break
            for raw in items:
                if not isinstance(raw, dict):
                    continue
                parsed = parse_library_item(raw)
                if not parsed:
                    continue
                upsert_item(conn, parsed)
                total += 1
            if progress:
                progress(total, page)
            if len(items) < page_size:
                break
            page += 1
    conn.commit()
    conn.close()
    return total
