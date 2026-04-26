# Architecture — stake-mirrors-ping

## Overview

Async Python CLI tool that tests network latency to Stake.com mirror sites with Rich terminal UI.

## Module Map

```
src/
├── main.py          ← CLI entry + async orchestration
├── pinger.py        ← TCP, HTTPS, DNS latency tests (semaphore-bounded)
├── dns_resolver.py  ← GeoIP enrichment via ip-api.com
├── stake_api.py     ← GraphQL latency + $0 dice bet benchmarks (curl_cffi)
├── nordvpn.py       ← VPN server fetch, haversine distance, latency estimation
├── reporter.py      ← Rich table output, JSON/CSV export
├── dashboard.py     ← Live auto-refresh terminal UI
├── history.py       ← SQLite persistence + uptime stats
└── models.py        ← Dataclasses (MirrorConfig, PingResult, NordVPNServer)
```

## Data Flow

1. Load mirrors from `config.yaml`
2. Concurrent ping (TCP + HTTPS + DNS) via `asyncio.Semaphore`
3. Optional: GraphQL API latency + dice bet benchmark
4. Optional: NordVPN server recommendations (haversine proximity)
5. Results → Rich tables / JSON / CSV / SQLite history

## Key Design Decisions

- `curl_cffi` for Cloudflare TLS fingerprint bypass
- GeoIP via ip-api.com free tier (45 req/min, cached)
- SQLite append-only history (never delete scan results)
- `config.yaml` is single source of truth for mirrors
