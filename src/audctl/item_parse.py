"""Normalize Audible 1.0/library item payloads (shape varies by response_groups)."""

from __future__ import annotations

import json
from typing import Any


def _names(seq: Any) -> list[str]:
    if not isinstance(seq, list):
        return []
    out: list[str] = []
    for el in seq:
        if isinstance(el, str):
            out.append(el)
        elif isinstance(el, dict):
            n = el.get("name")
            if isinstance(n, str):
                out.append(n)
    return out


def parse_library_item(item: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    asin = item.get("asin") or item.get("product_asin")
    if not isinstance(asin, str) or len(asin) != 10:
        return None

    title = item.get("title")
    if not isinstance(title, str) or not title.strip():
        pd = item.get("product_description")
        if isinstance(pd, dict):
            t2 = pd.get("title")
            if isinstance(t2, str):
                title = t2
    if not isinstance(title, str) or not title.strip():
        title = asin

    authors = _names(item.get("authors"))
    narrators = _names(item.get("narrators"))

    runtime = item.get("runtime_length_min")
    if runtime is None:
        runtime = item.get("length_minutes")
    try:
        runtime_minutes = int(runtime) if runtime is not None else None
    except (TypeError, ValueError):
        runtime_minutes = None

    series_title: str | None = None
    series_sequence: str | None = None
    series = item.get("series")
    if isinstance(series, list) and series:
        first = series[0]
        if isinstance(first, dict):
            st = first.get("title")
            if isinstance(st, str):
                series_title = st
            ss = first.get("sequence")
            if isinstance(ss, (str, int, float)):
                series_sequence = str(ss)

    purchase_date = item.get("purchase_date")
    if not isinstance(purchase_date, str):
        purchase_date = item.get("order_date")
    if not isinstance(purchase_date, str):
        purchase_date = None

    return {
        "asin": asin.upper(),
        "title": title.strip(),
        "authors": authors,
        "narrators": narrators,
        "runtime_minutes": runtime_minutes,
        "series_title": series_title,
        "series_sequence": series_sequence,
        "purchase_date": purchase_date,
        "raw_json": json.dumps(item, ensure_ascii=False),
    }
