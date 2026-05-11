# Contributing

Thank you for helping improve audctl.

## Principles

- **Scope:** Keep changes focused on the issue or feature; avoid unrelated refactors.
- **Honesty:** This tool wraps Audible’s **web** experience and an **unofficial** metadata API. Do not imply official Amazon support or DRM circumvention.
- **Security:** Do not commit credentials, real ASINs from private libraries, or stack traces with tokens. The HTTP `serve` mode is intentionally unauthenticated—document risks, do not weaken localhost defaults without discussion.

## Development

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## Pull requests

- Describe **what** changed and **why** in plain language.
- Add or update tests when behavior changes.
- Match existing style (Typer CLI, small modules under `src/audctl/`).

## Repository

Upstream lives at [github.com/SkyeClover/AudibleFromTheCommandLine](https://github.com/SkyeClover/AudibleFromTheCommandLine). **`[project.urls]`** in `pyproject.toml` and the README CI badge point there; update them if you maintain a long-lived fork as the new canonical home.

## Publishing checklist (forks / new remotes)

1. Add your remote and push (if this is a fresh checkout without `origin`):

   ```bash
   git remote add origin https://github.com/SkyeClover/AudibleFromTheCommandLine.git
   git branch -M main
   git push -u origin main
   ```

2. Confirm GitHub **Actions** are enabled so the CI workflow runs on `main`.
