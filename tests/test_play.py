from pathlib import Path

from audctl.play import build_chromium_argv


def test_build_chromium_argv_order() -> None:
    argv = build_chromium_argv(
        binary="/bin/chromium",
        profile_dir=Path("/tmp/p"),
        url="https://example.com",
        headless=True,
    )
    assert argv[0] == "/bin/chromium"
    assert "--headless=new" in argv
    assert any(a.startswith("--user-data-dir=") for a in argv)
    assert argv[-1] == "https://example.com"


def test_build_chromium_argv_no_headless() -> None:
    argv = build_chromium_argv(
        binary="/bin/chromium",
        profile_dir=Path("/tmp/p"),
        url="https://example.com",
        headless=False,
    )
    assert "--headless=new" not in argv
