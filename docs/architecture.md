# Architecture — stake-mirrors-ping

## Overview

Async Python CLI tool + Electron desktop GUI that tests network latency to Stake.com mirror sites with Rich terminal UI.

## Module Map

```
src/
├── main.py              ← CLI entry + async orchestration
├── core/
│   ├── __init__.py      ← Clean API export (OrchestratorConfig, run_scan, serializers)
│   ├── orchestrator.py  ← CLI-independent core logic (OrchestratorConfig, run_scan, ScanResult)
│   ├── serializers.py   ← Pydantic v2 schemas for JSON export
│   └── api.py           ← JSON-RPC server for GUI communication
├── pinger.py            ← TCP, HTTPS, DNS latency tests (semaphore-bounded)
├── dns_resolver.py      ← GeoIP enrichment via ip-api.com
├── stake_api.py         ← GraphQL latency + $0 dice bet benchmarks (curl_cffi)
├── nordvpn.py           ← VPN server fetch, haversine distance, latency estimation
├── reporter.py          ← Rich table output, JSON/CSV export
├── dashboard.py         ← Live auto-refresh terminal UI
├── history.py           ← HistoryDB class with context manager, SQLite persistence
└── models.py            ← Dataclasses (MirrorConfig, PingResult, NordVPNServer)

gui/
├── main.js              ← Electron main process, Python subprocess spawning
├── preload.js           ← Context bridge for IPC
├── renderer.js          ← UI logic, tab switching, scan execution
├── index.html           ← Single-page app with mirrors, dashboard, history, settings tabs
└── package.json         ← Electron + electron-builder config
```

## Data Flow

### CLI Path
1. Load mirrors from `config.yaml`
2. Concurrent ping (TCP + HTTPS + DNS) via `asyncio.Semaphore`
3. Optional: GraphQL API latency + dice bet benchmark
4. Optional: NordVPN server recommendations (haversine proximity)
5. Results → Rich tables / JSON / CSV / SQLite history

### GUI Path
1. Electron main process spawns Python subprocess via `src/core/api.py`
2. GUI sends JSON-RPC commands (run-scan, get-history-stats, etc.)
3. Python core executes scan via `OrchestratorConfig` and `run_scan()`
4. Results serialized via Pydantic schemas and returned as JSON
5. GUI renders results in mirrors/dashboard/history tabs

## Key Design Decisions

- `curl_cffi` for Cloudflare TLS fingerprint bypass
- GeoIP via ip-api.com free tier (45 req/min, cached)
- SQLite append-only history (never delete scan results)
- `config.yaml` is single source of truth for mirrors
- Core API layer is CLI-independent for GUI reuse
- Pydantic v2 for data validation and serialization
- GUI communicates via JSON-RPC through Python subprocess
- HistoryDB uses context manager for resource cleanup
