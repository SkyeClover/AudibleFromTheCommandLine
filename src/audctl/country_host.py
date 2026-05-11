"""Map Audible marketplace country code to www.audible.* host for web player URLs."""

from __future__ import annotations

# Keys match `audible.localization.LOCALE_TEMPLATES` country_code values.
_DOMAIN_BY_COUNTRY: dict[str, str] = {
    "us": "com",
    "uk": "co.uk",
    "de": "de",
    "fr": "fr",
    "ca": "ca",
    "it": "it",
    "au": "com.au",
    "in": "in",
    "jp": "co.jp",
    "es": "es",
}


def audible_host_for_country(country_code: str) -> str:
    cc = country_code.strip().lower()
    dom = _DOMAIN_BY_COUNTRY.get(cc, "com")
    return f"www.audible.{dom}"
