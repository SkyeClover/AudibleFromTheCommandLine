# audctl

Terminal-first helper for **your** Audible library: sign in once (including SMS / authenticator prompts), **index titles and ASINs** into a local SQLite database, then open the **normal web player** by title without clicking through the library every time.

Playback still happens in a **browser** (Chromium/Chrome/Edge when available, otherwise your OS default). DRM stays in the browser. This project is **not affiliated with Audible or Amazon** and is **not** an official product; the library list uses the **unofficial** [`audible`](https://pypi.org/project/audible/) Python package (internal API), which can break if Amazon changes endpoints or policies.

**Contributing:** see [CONTRIBUTING.md](CONTRIBUTING.md). **Security:** see [SECURITY.md](SECURITY.md).

## Typical workflow

### First start

1. Run **`audctl`** with no arguments (or `audctl setup` first if you prefer explicit steps).
2. If no API credentials exist yet, you are prompted for **email** and **password** (password is hidden). Amazon may ask for **authenticator codes**, **SMS/email codes**, or a **CAPTCHA**—follow the on-screen prompts. Wrong password / account lockouts surface as clear errors instead of a generic failure. At the **SMS/email verification** step, the tool submits Amazon’s page first (so a code can actually be sent), then offers **`[r]` resend** if the page exposes a resend control—if nothing arrives, check spam, wait a minute, confirm **`-m` marketplace** matches your account, or finish sign-in in a normal browser.
3. You are offered a **browser** for a one-time **web** login as well (Chromium/Chrome/Edge when available, otherwise the OS default—see `AUDCTL_PREFER_DEFAULT_BROWSER`). Accept unless you only care about metadata: the web player needs browser cookies for audio.
4. Your library is **synced** into `$XDG_STATE_HOME/audctl/library.db` (ASIN, title, authors, narrators, runtime when the API returns them).
5. A **terminal UI** opens: filter with `/`, **S** sync, **T** toggle “tracked”, **P** open the web player for the selected row (same browser strategy as `audctl play`).

### Every later start

- Run **`audctl`** (or **`audctl tui`**) to open the same UI. Use **`audctl sync`** to refresh the index after new purchases.

### Command-line play by title

After sync, `audctl play --title "…"` resolves against the SQLite index (tracked titles first), then opens `/webplayer?asin=…`. If Chromium/Chrome/Edge is not on `PATH`, **`audctl play` falls back to the system default browser** using the same multi-strategy opener as web login (`webbrowser`, then Windows `start` / `rundll32`, `xdg-open`, etc.). If every method fails, the URL is printed and the command exits with code **7**—set `AUDCTL_CHROMIUM_BINARY` or open the printed URL manually.

### Test the whole flow again (clean slate)

From the project directory (with your venv activated if you use one):

```powershell
audctl reset --force --yes --purge-browser-profile
```

That removes **API credentials** (`audible_credentials.json`), **library index** (`library.db`), optional legacy **`library_index.json`**, and optionally the **audctl Chromium profile** (web cookies). It does **not** delete `$XDG_CONFIG_HOME/audctl/config.toml` (marketplace, paths, etc.).

Then run:

```powershell
audctl
```

You should get the first-time prompts again (or run `audctl setup` explicitly).

### Log out / reset (what exists today)

| Goal | Command |
|------|---------|
| **Full local reset** (re-test setup from scratch) | `audctl reset --force` then confirm; add `--yes` to skip the prompt; add `--purge-browser-profile` to also wipe the Chromium data dir. |
| **Web session only** (Chromium cookies for `audctl play`) | Sign out in the browser, or `audctl logout --purge-profile --force`. |
| **Amazon account** | Use Amazon / Audible account pages to sign out or remove “Audible on iPhone” style devices; audctl cannot change your Amazon password. |

## Requirements

- **Python** 3.10 or newer (3.13 supported; the `audible` wheel set may lag on very new interpreters—see PyPI).
- Network access for login and sync.

## Install

From a clone of this repository (replace the URL with your fork or upstream):

```bash
git clone <repository-url>
cd Audible_FromTheCommandLine
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Or install the directory in place with **pipx** (no dev extras):

```bash
pipx install /path/to/audctl
```

Entry point: **`audctl`** (or **`python -m audctl`**).

## TUI keys

| Key | Action |
|-----|--------|
| `/` | Focus the filter box |
| `S` | Re-sync library from Audible (background) |
| `T` | Toggle “tracked” for the highlighted row |
| `P` | Open web player for that ASIN (Chromium or default browser) |
| `Q` | Quit |

## Commands

| Command | Description |
|---------|-------------|
| *(no args)* | First-time setup if needed, then TUI. |
| `audctl setup` | API login wizard (`-m` / `--marketplace` for country code). |
| `audctl sync` | Refresh SQLite index from your library. |
| `audctl tui` | Open the TUI only. |
| `audctl login` | Web sign-in for playback cookies (Chromium when available, else default browser). |
| `audctl play` / `resolve` / `urls` / `stop` / … | Same as before (see `--help`). |
| `audctl init-config` | Write `config.toml` (`--marketplace` sets host + country together). |
| `audctl status` | Profile paths, API credential presence, library row count. |
| `audctl reset` | Delete local credentials + library DB (+ optional `--purge-browser-profile`). Requires `--force`; use `--yes` for scripts. |
| `audctl logout` | Instructions, or `--purge-profile --force` to delete only the Chromium profile. |
| `audctl serve` | **HTTP JSON API** on `http://127.0.0.1:8765` by default (see below). |

## HTTP API (`audctl serve`)

Run on the machine that has your Audible login / browser (or use `host.docker.internal` from a container with correct networking).

```bash
audctl serve --host 127.0.0.1 --port 8765
```

**Discovery:** `GET /` returns a list of routes and short descriptions.

| Method | Path | Body (JSON) | Response |
|--------|------|-------------|----------|
| `GET` | `/` | — | Service name, version, endpoint list. |
| `GET` | `/health` | — | `{ "status": "ok" }` |
| `GET` | `/v1/status` | — | Same fields as `audctl status` (paths, `library_items`, credentials present, …). |
| `POST` | `/v1/play` | `{ "asin": "B0…", "headless": false }` | Opens web player; returns `via`, `pid` (if Chromium), `url`. |
| `POST` | `/v1/sync` | `{}` | Refreshes library DB (requires prior `audctl setup`). |
| `POST` | `/v1/resolve` | `{ "title": "…" }` and/or `{ "asin": "B0…" }` | `{ "ok": true, "result": { … } }` (same shape as CLI `resolve --json`). |

Examples:

```bash
curl -sS http://127.0.0.1:8765/
curl -sS http://127.0.0.1:8765/v1/status
curl -sS -X POST http://127.0.0.1:8765/v1/play -H 'Content-Type: application/json' -d '{"asin":"B012345678","headless":false}'
curl -sS -X POST http://127.0.0.1:8765/v1/resolve -H 'Content-Type: application/json' -d '{"title":"Some Book"}'
curl -sS -X POST http://127.0.0.1:8765/v1/sync -H 'Content-Type: application/json' -d '{}'
```

**Security:** there is **no authentication** and responses use **CORS `*`** for simple local scripting. Bind to **`127.0.0.1`** only; if you must expose it, put **TLS + auth** (reverse proxy, API gateway) in front.

## What works vs caveats

| Area | Works | Caveats |
|------|--------|---------|
| **Library index** | `audctl sync` via unofficial `audible` client; SQLite for fast local match. | Subject to Amazon / Audible changes; respect their ToS. |
| **2FA / SMS** | Prompted in the terminal during `setup`. | CAPTCHA flows may need you to read a URL or image per Amazon’s challenge. |
| **Playback** | Chromium + official web player URL. | Separate from API tokens—you still need a logged-in browser profile for audio. |
| **Snap Chromium** | `SNAP_USER_COMMON` default profile path. | You may need `AUDCTL_CHROMIUM_PROFILE_DIR` under `~/snap/chromium/common/…` if SingletonLock errors appear. |

## Configuration

| Variable / file | Purpose |
|-----------------|--------|
| `$XDG_CONFIG_HOME/audctl/config.toml` | `audible_host`, `marketplace_country`, `chromium_profile_dir`, etc. |
| `$AUDCTL_MARKETPLACE` | Marketplace country code (`us`, `uk`, …). |
| `$AUDCTL_AUDIBLE_HOST` | Override web host for player URLs. |
| `$AUDCTL_CHROMIUM_PROFILE_DIR` | Chromium profile for web session. |
| `$AUDCTL_PREFER_DEFAULT_BROWSER` | If `1` / `true`, skip Chromium and always use the OS default browser for web login. |
| `$AUDCTL_ALLOW_SEARCH_SCRAPE` | Last-resort HTML search for `resolve` when nothing else matches. |
| `$AUDCTL_LIBRARY_INDEX` | Legacy JSON `[{title, asin}]` if you still use it (SQLite is preferred). |

API credentials are stored under `$XDG_STATE_HOME/audctl/audible_credentials.json` (encrypted by the `audible` library). Config files written by `audctl init-config` use mode **600** on POSIX.

## License

MIT — see [LICENSE](LICENSE). Changelog: [CHANGELOG.md](CHANGELOG.md).

## Development

```bash
pip install -e ".[dev]"
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for branching, PR expectations, and the checklist after you create the GitHub remote (e.g. add `[project.urls]` in `pyproject.toml`). CI runs **pytest** on Ubuntu and Windows for Python 3.10–3.13 (see `.github/workflows/ci.yml`).

## Stretch ideas

- MPRIS / `playerctl` for pause–resume.
- Home Assistant–friendly envelopes for `serve`.
