"""Desktop progress is additive to the core API and reports actual completions."""

import asyncio

from src import pinger
from src.models import MirrorConfig, PingResult


def test_progress_reports_completions_without_changing_result_order(monkeypatch):
    mirrors = [MirrorConfig(f"stake{i}.com", f"https://stake{i}.com") for i in range(3)]
    events = []

    async def ping(mirror, rounds, timeout):
        await asyncio.sleep(0)
        return PingResult(mirror)

    monkeypatch.setattr(pinger, "ping_mirror", ping)
    result = asyncio.run(
        pinger.ping_all_mirrors(
            mirrors, progress=lambda done, total: events.append((done, total))
        )
    )
    assert [r.mirror for r in result] == mirrors
    assert events == [(1, 3), (2, 3), (3, 3)]
