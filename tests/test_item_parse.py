from audctl.item_parse import parse_library_item


def test_parse_flat_item() -> None:
    row = parse_library_item(
        {
            "asin": "b012345678",
            "title": "Example Book",
            "authors": [{"name": "A. Author"}],
            "narrators": [{"name": "N. Narrator"}],
            "runtime_length_min": 120,
        }
    )
    assert row is not None
    assert row["asin"] == "B012345678"
    assert row["title"] == "Example Book"
    assert row["authors"] == ["A. Author"]
    assert row["runtime_minutes"] == 120


def test_parse_missing_title_uses_asin() -> None:
    row = parse_library_item({"asin": "B099999999"})
    assert row is not None
    assert row["title"] == "B099999999"


def test_parse_invalid_returns_none() -> None:
    assert parse_library_item({}) is None
    assert parse_library_item({"asin": "short"}) is None
