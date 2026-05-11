"""Build Audible URLs without implying any private playback API."""

from __future__ import annotations

from urllib.parse import quote_plus


def _host(host: str) -> str:
    h = host.strip().lower()
    if h.startswith("http://") or h.startswith("https://"):
        return h.split("://", 1)[1].rstrip("/")
    return h.rstrip("/")


def store_url(*, host: str, asin: str) -> str:
    h = _host(host)
    return f"https://{h}/pd/{asin}"


def webplayer_url(*, host: str, asin: str) -> str:
    h = _host(host)
    return f"https://{h}/webplayer?asin={asin}"


def search_url(*, host: str, query: str) -> str:
    h = _host(host)
    q = quote_plus(query)
    return f"https://{h}/search?keywords={q}"
