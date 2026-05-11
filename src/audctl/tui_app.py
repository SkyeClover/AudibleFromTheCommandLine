"""Simple Textual UI: browse synced library, toggle tracked, sync, play."""

from __future__ import annotations

import threading

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Input

from audctl.auth_setup import load_authenticator
from audctl.config import AudctlConfig
from audctl.db import LibraryRow, connect, init_schema, iter_rows, set_tracked
from audctl.library_sync import sync_library_to_db
from audctl.paths import library_db_path
from audctl.play import launch_web_player
from audctl.urls import webplayer_url


class LibraryApp(App[None]):
    """Terminal UI for the local library index."""

    CSS = """
    DataTable { height: 1fr; }
    Input { dock: top; height: 1; margin: 0 1; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("s", "sync", "Sync", show=True),
        Binding("t", "toggle_tracked", "Track", show=True),
        Binding("p", "play", "Play", show=True),
        Binding("slash", "focus_filter", "Filter", show=True),
    ]

    def __init__(self, cfg: AudctlConfig) -> None:
        super().__init__()
        self._cfg = cfg
        self._rows: list[LibraryRow] = []
        self._filter = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Input(placeholder="Filter titles (type, then click table). Press / to focus.")
        yield DataTable(cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("•", "Title", "Authors", "ASIN")
        self.reload_table()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._filter = event.value
        self.reload_table()

    def reload_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=False)
        self._rows = []
        dbp = library_db_path()
        if not dbp.is_file():
            return
        conn = connect(dbp)
        init_schema(conn)
        for row in iter_rows(conn, tracked_only=False, query=self._filter or None):
            self._rows.append(row)
            mark = "Y" if row.tracked else " "
            authors = ", ".join(row.authors[:2])
            if len(row.authors) > 2:
                authors += "…"
            table.add_row(mark, row.title, authors or "—", row.asin)
        conn.close()

    def action_focus_filter(self) -> None:
        self.query_one(Input).focus()

    def action_sync(self) -> None:
        self.notify("Syncing library from Audible…")

        def job() -> tuple[int, str | None]:
            try:
                auth = load_authenticator()
                n = sync_library_to_db(auth=auth, country_code=self._cfg.marketplace_country)
                return n, None
            except Exception as exc:  # noqa: BLE001 — show user-facing error
                return 0, str(exc)

        def done(res: tuple[int, str | None]) -> None:
            n, err = res
            if err:
                self.notify(f"Sync failed: {err}", severity="error", timeout=10)
            else:
                self.notify(f"Synced {n} item(s).", timeout=6)
            self.reload_table()

        def thread_main() -> None:
            res = job()
            self.call_from_thread(done, res)

        threading.Thread(target=thread_main, daemon=True).start()

    def _selected_row(self) -> LibraryRow | None:
        table = self.query_one(DataTable)
        if not self._rows:
            return None
        cr = table.cursor_row
        if cr is None or cr < 0 or cr >= len(self._rows):
            return None
        return self._rows[cr]

    def action_toggle_tracked(self) -> None:
        row = self._selected_row()
        if row is None:
            self.notify("Select a row first.", severity="warning")
            return
        dbp = library_db_path()
        conn = connect(dbp)
        init_schema(conn)
        set_tracked(conn, row.asin, not row.tracked)
        conn.close()
        self.reload_table()

    def action_play(self) -> None:
        row = self._selected_row()
        if row is None:
            self.notify("Select a row first.", severity="warning")
            return
        url = webplayer_url(host=self._cfg.audible_host, asin=row.asin)
        self.notify(f"Opening web player…")

        def job() -> tuple[bool, str | None]:
            try:
                out = launch_web_player(
                    binary=self._cfg.chromium_binary,
                    profile_dir=self._cfg.chromium_profile_dir,
                    url=url,
                    headless=False,
                    dry_run=False,
                )
                if out.get("via") == "default_browser" and not out.get("opened"):
                    return False, "Could not open default browser; set AUDCTL_CHROMIUM_BINARY or open the URL manually."
                return True, None
            except Exception as exc:  # noqa: BLE001
                return False, str(exc)

        def done(res: tuple[bool, str | None]) -> None:
            ok, err = res
            if err:
                self.notify(f"Play failed: {err}", severity="error", timeout=10)
            else:
                self.notify("Browser launched.", timeout=4)

        def thread_main() -> None:
            res = job()
            self.call_from_thread(done, res)

        threading.Thread(target=thread_main, daemon=True).start()


def run_library_tui(cfg: AudctlConfig) -> None:
    LibraryApp(cfg).run()
