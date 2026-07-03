# Stake Mirrors Ping 🏓

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![GitHub stars](https://img.shields.io/github/stars/subkoks/stake-mirrors-ping.svg?style=social&label=Star)](https://github.com/subkoks/stake-mirrors-ping)
[![GitHub issues](https://img.shields.io/github/issues/subkoks/stake-mirrors-ping.svg)](https://github.com/subkoks/stake-mirrors-ping/issues)

Find the fastest Stake.com mirror site + optimal NordVPN region for lowest latency.

## Features

- **16 Stake mirrors** tested concurrently (TCP + HTTPS + DNS)
- **GeoIP lookup** — see where each mirror's server is located
- **NordVPN recommendations** — best EU server city per mirror
- **Stake API integration** — GraphQL latency via `curl_cffi` (Chrome TLS fingerprint bypasses Cloudflare)
- **Live dashboard** — real-time auto-refreshing terminal UI with `rich.live`
- **History tracking** — SQLite-based latency history with uptime stats
- **Rich CLI** — color-coded sorted table, fastest on top
- **Export** — save results to JSON or CSV

## Quick Start

```bash
# Activate venv
source .venv/bin/activate

# Basic ping test (no API key needed)
python -m src.main

# With API latency tests
cp .env.example .env  # add your STAKE_SESSION_TOKEN
python -m src.main --api

# With $0 Dice bet latency benchmark
python -m src.main --api --benchmark-bets

# Export results
python -m src.main --export json
python -m src.main --export csv

# Live dashboard (refresh every 30s)
python -m src.main --live 30

# Live dashboard with API tests
python -m src.main --live 30 --api --skip-vpn

# View uptime history stats
python -m src.main --history

# Skip NordVPN / GeoIP
python -m src.main --skip-vpn --skip-geoip

# Custom rounds and timeout
python -m src.main --rounds 5 --timeout 15
```

## Stake API Setup (Optional)

1. Open Stake.com in your browser
2. Open DevTools (F12) → Application → Cookies
3. Copy the `session` cookie value
4. Create `.env` file:

   ```text
   STAKE_SESSION_TOKEN=your_session_token_here
   ```

5. Run with `--api` flag

## CLI Options

| Flag                | Description                               |
| ------------------- | ----------------------------------------- |
| `--config FILE`     | Custom config file (default: config.yaml) |
| `--rounds N`        | Number of ping rounds (default: 3)        |
| `--timeout N`       | Timeout in seconds (default: 10)          |
| `--api`             | Enable Stake API latency tests            |
| `--benchmark-bets`  | Enable $0 Dice bet latency test           |
| `--skip-geoip`      | Skip GeoIP lookups                        |
| `--skip-vpn`        | Skip NordVPN recommendations              |
| `--export json/csv` | Export results to file                    |
| `--output-dir DIR`  | Output directory (default: results/)      |
| `--live SECONDS`    | Live dashboard with auto-refresh          |
| `--watch SECONDS`   | Legacy continuous monitoring              |
| `--history`         | Show uptime stats from history.db         |
| `--no-history`      | Don't save results to history.db          |

## Output Example

```text
┌───┬──────────────┬────────┬─────────────────┬──────────────────┬────────┬────────┬────────┬───────┐
│ # │ Mirror       │ Status │ IP              │ Location         │ TCP    │ HTTPS  │ API    │ Best  │
├───┼──────────────┼────────┼─────────────────┼──────────────────┼────────┼────────┼────────┼───────┤
│ 1 │ stake.bet 🔒 │ ✓ UP   │ 104.22.10.123   │ London, UK       │ 12.3ms │ 45.6ms │ 89.1ms │ 12.3ms│
│ 2 │ stake.ac 🔒  │ ✓ UP   │ 172.67.182.45   │ Amsterdam, NL    │ 18.7ms │ 52.3ms │ 95.4ms │ 18.7ms│
│ ...                                                                                              │
└───┴──────────────┴────────┴─────────────────┴──────────────────┴────────┴────────┴────────┴───────┘

🏆 FASTEST MIRROR: stake.bet — 12.3ms

🎯 RECOMMENDED: NordVPN → London, UK → stake.bet (Est. 27.3ms)
```

## Config

Edit `config.yaml` to add/remove mirrors, change settings, or modify NordVPN target regions.

## Tech Stack

- Python 3.12+ with asyncio
- curl_cffi (Chrome TLS fingerprint — bypasses Cloudflare)
- aiohttp + aiodns (async HTTP/DNS)
- rich (beautiful CLI output + live dashboard)
- SQLite (history tracking)
- PyYAML + python-dotenv (config)

## Codex CLI

Codex CLI can use the repo root `AGENTS.md` and the tracked `.codex/config.toml` defaults in this workspace.
