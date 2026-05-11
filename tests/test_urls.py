import pytest

from audctl.urls import search_url, store_url, webplayer_url


def test_webplayer_url() -> None:
    assert (
        webplayer_url(host="www.audible.com", asin="B0ABCDEFGH")
        == "https://www.audible.com/webplayer?asin=B0ABCDEFGH"
    )


def test_store_url() -> None:
    assert store_url(host="www.audible.co.uk", asin="B0ABCDEFGH") == (
        "https://www.audible.co.uk/pd/B0ABCDEFGH"
    )


def test_search_url_encodes() -> None:
    u = search_url(host="www.audible.com", query="14 by Peter Clines")
    assert "keywords=" in u
    assert "Peter" in u


@pytest.mark.parametrize(
    "host",
    ["https://www.audible.de", "www.audible.de"],
)
def test_host_strips_scheme(host: str) -> None:
    assert webplayer_url(host=host, asin="B012345678").startswith("https://www.audible.de/")
