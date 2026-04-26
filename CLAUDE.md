# Project Rules — stake-mirrors-ping

## Project Overview

- **Name:** stake-mirrors-ping
- **Type:** CLI tool — network latency tester for Stake.com mirror sites
- **Stack:** Python 3.12+ / aiohttp, curl_cffi, Rich, SQLite
- **Version:** 1.0.0
- **Repo:** github.com/subkoks/stake-mirrors-ping

## Architecture

- **Entry point:** `src/main.py` — CLI arg parsing + async orchestration
- **Pinger:** `src/pinger.py` — TCP, HTTPS, DNS latency tests with concurrent semaphore
- **DNS resolver:** `src/dns_resolver.py` — GeoIP enrichment via ip-api.com
- **Stake API:** `src/stake_api.py` — GraphQL latency + $0 dice bet benchmarks via curl_cffi
- **NordVPN:** `src/nordvpn.py` — fetch VPN servers, haversine distance, latency estimation
- **Reporter:** `src/reporter.py` — Rich table output, JSON/CSV export
- **Dashboard:** `src/dashboard.py` — Live auto-refresh terminal UI
- **History:** `src/history.py` — SQLite persistence + uptime stats
- **Models:** `src/models.py` — dataclasses (MirrorConfig, PingResult, NordVPNServer, VPNRecommendation)

## Key Files

- `config.yaml` — 16 mirrors, ping settings, NordVPN target regions
- `src/models.py` — all data structures
- `src/pinger.py` — core ping logic
- `src/history.py` — SQLite schema and queries
- `pyproject.toml` — project config (black, isort, ruff, mypy)
- `.env.example` — STAKE_SESSION_TOKEN template

## Commands

- **Basic run:** `python -m src.main`
- **With API tests:** `python -m src.main --api`
- **With bet benchmark:** `python -m src.main --api --benchmark-bets`
- **Live dashboard:** `python -m src.main --live 30`
- **Export JSON:** `python -m src.main --export json`
- **Export CSV:** `python -m src.main --export csv`
- **History stats:** `python -m src.main --history`
- **Skip VPN:** `python -m src.main --skip-vpn`
- **Tests:** `python -m pytest tests/ -v`

## Environment Variables

- `STAKE_SESSION_TOKEN` — Stake session JWT for API tests (optional, from .env)

## Project Conventions

- Async everywhere: all network operations use `asyncio` + `aiohttp`
- Concurrent pinging via `asyncio.Semaphore(concurrency)`
- Rich console for all CLI output (progress bars, tables, panels)
- SQLite for history persistence (`history.db` at project root)
- Parameterized SQL queries (no string interpolation)
- `curl_cffi` for Cloudflare TLS fingerprint bypass in API tests
- GeoIP via ip-api.com free tier (45 req/min, 1.5s delay between calls)
- Haversine distance for VPN server proximity calculation

## Project-Specific Rules

- Keep all ping operations non-blocking (async)
- Never hardcode Stake domains — read from `config.yaml`
- STAKE_SESSION_TOKEN must never be logged or exported
- GeoIP results should be cached where possible (rate limit sensitive)
- History DB is append-only — never delete scan results
- `config.yaml` is the single source of truth for mirrors and settings
- Run `python -m pytest tests/ -v` before committing
