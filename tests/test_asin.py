import pytest

from audctl.asin import is_valid_asin, normalize_asin, validate_asin


def test_normalize_uppercases() -> None:
    assert normalize_asin("b012345678") == "B012345678"


@pytest.mark.parametrize(
    "raw,ok",
    [
        ("B012345678", True),
        ("123456789X", True),
        ("B01234567", False),
        ("B0123456789", False),
        ("", False),
        ("b012345678", True),
    ],
)
def test_is_valid_asin(raw: str, ok: bool) -> None:
    assert is_valid_asin(raw) is ok


def test_validate_asin_raises() -> None:
    with pytest.raises(ValueError):
        validate_asin("short")
