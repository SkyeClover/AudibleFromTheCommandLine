# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- HTTP API: `POST /v1/stop` to signal Chromium processes using the configured profile (`signal`: `term` or `kill`).
- HTTP API: `POST /v1/play` accepts `title` (resolve via library index / optional search scrape) plus `offscreen`, `offscreen_position`, `headless`.
- Optional bearer auth: set `AUDCTL_HTTP_TOKEN`; send `Authorization: Bearer …` for all routes except `GET /` and `GET /health`.
- CLI `audctl play --offscreen` and Chromium `--window-position` via `AUDCTL_CHROME_OFFSCREEN_POSITION`.

## [0.1.0] - 2026-05-11

### Added

- Initial release: Typer CLI, Textual library TUI, SQLite sync via unofficial `audible` API, Chromium / default-browser web player launch, `audctl serve` JSON HTTP API, login/CVF improvements, reset/logout flows, tests and documentation.
