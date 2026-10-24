"""Developer-only offline transport: run the real bridge with a mocked scanner."""

import asyncio
import os
import runpy
import subprocess
import sys
from pathlib import Path

if sys.argv[1:3] == ["-I", "-c"]:
    raise SystemExit(
        subprocess.run([sys.executable, *sys.argv[1:]], check=False).returncode
    )

if sys.argv[1] == "-I":
    sys.argv.pop(1)


def main():
    script = Path(sys.argv[1])
    sys.path.insert(0, str(script.parent.parent.parent))
    import src.core
    from src.core.orchestrator import ScanResult
    from src.history import HistoryDB
    from src.models import PingResult

    async def offline_scan(config):
        data = Path(os.environ["STAKE_DATA_DIR"])
        (data / "scan.pid").write_text(str(os.getpid()))
        mode = (
            (data / "scenario.txt").read_text()
            if (data / "scenario.txt").exists()
            else "fast"
        )
        await asyncio.sleep(30 if mode == "slow" else 0.2)
        mirrors = src.core.parse_mirrors(src.core.load_config())
        results = [
            PingResult(
                m,
                is_up=True,
                https_latency_ms=float(i + 20),
                reachability="http_responding",
            )
            for i, m in enumerate(mirrors)
        ]
        results[1].https_latency_ms = 0.0
        for index, status in [
            (2, "dns_error"),
            (3, "blocked_or_challenged"),
            (4, "rate_limited"),
        ]:
            results[index].is_up = False
            results[index].reachability = status
            results[index].https_latency_ms = None
        if mode == "failed":
            for result in results:
                result.is_up = False
                result.reachability = "http_timeout"
        with HistoryDB(str(data / "history.db")) as db:
            db.save_results(results)
        return ScanResult(results, {}, "2026-10-24T00:00:00", mode)

    src.core.run_scan = offline_scan
    sys.argv = sys.argv[1:]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
