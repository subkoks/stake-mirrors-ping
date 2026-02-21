# Stake Mirrors Ping 🏓

Find the fastest Stake.com mirror site + optimal NordVPN region for lowest latency.

## Features

- **16 Stake mirrors** tested concurrently (TCP + HTTPS + DNS)
- **GeoIP lookup** — see where each mirror's server is located
- **NordVPN recommendations** — best EU server city per mirror
- **Stake API integration** — test real GraphQL/WebSocket/bet latency
- **Rich CLI** — color-coded sorted table, fastest on top
- **Export** — save results to JSON or CSV
- **Watch mode** — continuous monitoring with auto-refresh

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

# Watch mode (refresh every 60s)
python -m src.main --watch 60

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
| `--watch SECONDS`   | Continuous monitoring interval            |

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
- aiohttp + aiodns (async HTTP/DNS)
- websockets (WS latency testing)
- rich (beautiful CLI output)
- PyYAML + python-dotenv (config)
