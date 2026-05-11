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

## Publishing checklist (maintainers)

1. Create an empty GitHub repository (name it however you like; this checkout folder may stay `Audible_FromTheCommandLine`).
2. Push the first commit, for example:

   ```bash
   git init
   git add .
   git commit -m "Initial import"
   git branch -M main
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```

3. Add **`[project.urls]`** in `pyproject.toml` with real Homepage, Repository, and Issues URLs.
4. Optionally add a CI status badge to `README.md` pointing at your repo’s Actions tab.
