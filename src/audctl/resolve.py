"""Title → structured hints. No guarantee of correctness without human verification."""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

from audctl.asin import is_valid_asin, normalize_asin, validate_asin
from audctl.urls import search_url, store_url, webplayer_url


@dataclass
class ResolveResult:
    title: str
    asin: str | None
    confidence: float
    store_url: str | None = None
    webplayer_url: str | None = None
    search_url: str | None = None
    resolver: str = "unknown"
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = asdict(self)
        return d


_ASIN_IN_HTML = re.compile(r"\b(B[0-9A-Z]{9}|[0-9]{9}[A-Z])\b")


def resolve_from_asin(*, title: str, asin: str, host: str) -> ResolveResult:
    a = validate_asin(asin)
    return ResolveResult(
        title=title or a,
        asin=a,
        confidence=1.0,
        store_url=store_url(host=host, asin=a),
        webplayer_url=webplayer_url(host=host, asin=a),
        search_url=None,
        resolver="manual_asin",
        notes=["ASIN supplied explicitly; verify it matches the intended edition."],
    )


def resolve_title_only(*, title: str, host: str) -> ResolveResult:
    q = title.strip()
    return ResolveResult(
        title=q,
        asin=None,
        confidence=0.0,
        store_url=None,
        webplayer_url=None,
        search_url=search_url(host=host, query=q),
        resolver="title_fallback",
        notes=[
            "No ASIN inferred. Open search_url in a browser or pass --asin after verifying.",
        ],
    )


def _search_scrape_first_asin(*, title: str, host: str, timeout_s: float = 12.0) -> tuple[str | None, list[str]]:
    notes: list[str] = []
    url = search_url(host=host, query=title)
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "audctl/0.1 (opt-in search HTML resolution; no official Audible API)",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        notes.append(f"Search fetch failed: {exc!r}")
        return None, notes

    matches = _ASIN_IN_HTML.findall(body)
    for cand in matches:
        n = normalize_asin(cand)
        if is_valid_asin(n):
            notes.append(
                "Picked first ASIN-like token from public search HTML; "
                "Amazon markup changes often—verify before playback."
            )
            return n, notes
    notes.append("Search page returned no ASIN-like tokens audctl recognized.")
    return None, notes


def resolve_title(
    *,
    title: str,
    host: str,
    allow_search_scrape: bool,
) -> ResolveResult:
    q = title.strip()
    if not q:
        return ResolveResult(
            title="",
            asin=None,
            confidence=0.0,
            search_url=search_url(host=host, query=""),
            resolver="empty_query",
            notes=["Empty --title; nothing to resolve."],
        )

    if not allow_search_scrape:
        return resolve_title_only(title=q, host=host)

    asin, notes = _search_scrape_first_asin(title=q, host=host)
    if asin is None:
        base = resolve_title_only(title=q, host=host)
        base.resolver = "search_scrape_failed"
        base.notes = (base.notes or []) + notes
        return base

    a = validate_asin(asin)
    return ResolveResult(
        title=q,
        asin=a,
        confidence=0.35,
        store_url=store_url(host=host, asin=a),
        webplayer_url=webplayer_url(host=host, asin=a),
        search_url=search_url(host=host, query=q),
        resolver="search_scrape",
        notes=notes,
    )


def dumps_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"
