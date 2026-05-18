# Bugbot — stake-mirrors-ping review rules

## Security (blocking)

- Never commit `STAKE_SESSION_TOKEN`, NordVPN credentials, or `.env` contents.
- Flag logging of session tokens, cookies, or full HTTP headers with auth.
- Flag real-money bet benchmarks enabled by default — `--benchmark-bets` must stay opt-in.

## Python (`src/**`, `tests/**`)

- Async code: flag unawaited coroutines, blocking I/O inside async functions, and missing timeouts on `aiohttp` / `curl_cffi` calls.
- `history.py` SQLite: use parameterized queries; handle DB locked errors.
- Network: flag hardcoded mirror URLs changed without updating `config.yaml` docs.
- NordVPN / GeoIP: flag uncached external API spam (rate limits).

## Config (`config.yaml`)

- YAML changes must keep mirror list valid URLs and document new mirrors in `docs/architecture.md` when behavior changes.

## Docs-only PRs

- Non-blocking for README-only unless CLI flags or env vars are documented incorrectly.

## Before merge

- `pytest` passes; type/lint per `pyproject.toml` when Python changes.
