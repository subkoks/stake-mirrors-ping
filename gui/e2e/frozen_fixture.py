"""Separate test-build backend. This module is never collected in production."""

import asyncio
import os
from pathlib import Path

from src.core import api
from src.core.orchestrator import ScanResult, load_config, parse_mirrors
from src.history import HistoryDB
from src.models import PingResult


async def fixture_scan(config, progress=None):
    data = Path(os.environ["STAKE_DATA_DIR"])
    (data / "scan.pid").write_text(str(os.getpid()))
    mode = (
        (data / "scenario.txt").read_text()
        if (data / "scenario.txt").exists()
        else "partial"
    )
    mirrors = parse_mirrors(load_config())
    if progress:
        progress("Checking mirrors", 0, len(mirrors))
    if mode == "partial":
        async with asyncio.timeout(20):
            while not (data / "continue-scan").exists():
                await asyncio.sleep(0.02)
    else:
        await asyncio.sleep(30 if mode == "slow" else 0.3)
    results = [
        PingResult(
            m,
            is_up=True,
            https_latency_ms=float(i + 10),
            reachability="http_responding",
        )
        for i, m in enumerate(mirrors)
    ]
    for i, status in [
        (0, "dns_error"),
        (1, "blocked_or_challenged"),
        (2, "rate_limited"),
    ]:
        results[i].is_up = False
        results[i].https_latency_ms = None
        results[i].reachability = status
    if mode == "offline":
        for result in results:
            result.is_up = False
            result.https_latency_ms = None
            result.reachability = "dns_error"
    if mode == "empty":
        results = []
    if mode == "failure":
        raise RuntimeError(
            "The test scan engine could not complete the request. Retry the scan."
        )
    if progress:
        progress("Checking mirrors", len(mirrors), len(mirrors))
    if config.save_history:
        with HistoryDB(str(data / "history.db")) as db:
            db.save_results(results)
    return ScanResult(results, {}, "2026-10-24T00:00:00", mode)


api.run_scan = fixture_scan
if __name__ == "__main__":
    api.main()
