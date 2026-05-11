from unittest import mock

from audctl.resolve import resolve_title


def test_resolve_title_without_scrape_is_explicit() -> None:
    r = resolve_title(title="14 by Peter Clines", host="www.audible.com", allow_search_scrape=False)
    assert r.asin is None
    assert r.confidence == 0.0
    assert r.search_url is not None
    assert "search?" in r.search_url
    assert r.notes


def test_resolve_title_scrape_uses_first_asin() -> None:
    html = '<a href="/pd/B099999999/ref">x</a>'
    resp = mock.MagicMock()
    resp.read.return_value = html.encode()
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = None
    with mock.patch("audctl.resolve.urllib.request.urlopen", return_value=resp):
        r = resolve_title(title="anything", host="www.audible.com", allow_search_scrape=True)
    assert r.asin == "B099999999"
    assert r.confidence < 1.0
