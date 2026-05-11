"""ASIN validation (format-only; does not guarantee the title exists)."""

from __future__ import annotations

import re

_ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")


def normalize_asin(raw: str) -> str:
    return raw.strip().upper()


def is_valid_asin(candidate: str) -> bool:
    if not candidate:
        return False
    return bool(_ASIN_RE.match(normalize_asin(candidate)))


def validate_asin(candidate: str) -> str:
    """Return normalized ASIN or raise ValueError."""
    n = normalize_asin(candidate)
    if not is_valid_asin(n):
        raise ValueError(
            "ASIN must be exactly 10 uppercase letters/digits (Amazon product identifier)."
        )
    return n
