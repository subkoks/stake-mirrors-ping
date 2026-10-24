import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import MirrorConfig, PingResult
from src.pinger import classify_http, https_ping, ping_all_mirrors, ping_mirror


@pytest.mark.parametrize(
    "status,expected",
    [
        (200, "http_responding"),
        (403, "blocked_or_challenged"),
        (429, "rate_limited"),
        (302, "redirect_unverified"),
        (500, "http_error"),
        (None, "http_unavailable"),
    ],
)
def test_http_classification(status, expected):
    assert classify_http(status) == expected


def test_no_redirect_following_and_no_authenticity_claim():
    session = MagicMock()
    context = AsyncMock()
    context.__aenter__.return_value.status = 200
    session.head.return_value = context
    asyncio.run(https_ping("https://example.com", session=session))
    assert session.head.call_args.kwargs["allow_redirects"] is False
    assert (
        PingResult(
            MirrorConfig("example.com", "https://example.com")
        ).application_status
        == "unverified"
    )


def test_mixed_round_failure_cannot_win():
    mirror = MirrorConfig("example.com", "https://example.com")
    with (
        patch("src.pinger.dns_resolve", AsyncMock(return_value=("1.1.1.1", 1))),
        patch("src.pinger.tcp_ping", AsyncMock(return_value=1)),
        patch(
            "src.pinger.https_ping",
            AsyncMock(side_effect=[(20, 200, True), (5, 403, True)]),
        ),
    ):
        result = asyncio.run(ping_mirror(mirror, rounds=2))
    assert result.reachability == "blocked_or_challenged"
    assert not result.is_up and result.best_latency_ms is None


def test_large_scan_bounded_concurrency_and_cancellation():
    async def check():
        active = peak = completed = 0

        async def probe(mirror, *args):
            nonlocal active, peak, completed
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0.002)
                completed += 1
                return PingResult(mirror)
            finally:
                active -= 1

        mirrors = [
            MirrorConfig(f"mirror{i}.com", f"https://mirror{i}.com") for i in range(130)
        ]
        with patch("src.pinger.ping_mirror", probe):
            result = await ping_all_mirrors(mirrors, concurrency=4)
            assert len(result) == completed == len(mirrors) and peak <= 4
            task = asyncio.create_task(ping_all_mirrors(mirrors, concurrency=4))
            await asyncio.sleep(0.001)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert active == 0

    asyncio.run(check())


def test_ranking_is_https_only_and_missing_last():
    mirror = MirrorConfig("example.com", "https://example.com")
    fast_tcp = PingResult(
        mirror, tcp_latency_ms=1, https_latency_ms=20, api_latency_ms=0.5, is_up=True
    )
    zero = PingResult(mirror, https_latency_ms=0, is_up=True)
    failed = PingResult(mirror, tcp_latency_ms=0.1)
    assert fast_tcp.best_latency_ms == 20
    assert sorted([failed, fast_tcp, zero], key=lambda r: r.rank_key) == [
        zero,
        fast_tcp,
        failed,
    ]


def test_exports_and_history_support_expanded_inventory(tmp_path):
    import json
    from pathlib import Path

    from src.history import HistoryDB
    from src.reporter import export_results

    results = [
        PingResult(
            MirrorConfig(f"mirror{i}.com", f"https://mirror{i}.com"),
            is_up=True,
            https_latency_ms=float(130 - i),
            reachability="http_responding",
        )
        for i in range(130)
    ]
    export_results(results, {}, fmt="json", output_dir=str(tmp_path))
    payload = json.loads(next(Path(tmp_path).glob("*.json")).read_text())
    assert payload["scan"]["total_mirrors"] == len(results)
    assert payload["scan"]["fastest_mirror"] == "mirror129.com"
    assert all(r["application_status"] == "unverified" for r in payload["mirrors"])
    with HistoryDB(str(tmp_path / "history.db")) as db:
        assert db.save_results(results) == len(results)
        assert len(db.get_latest_scan()) == len(results)
        assert all(r["reachability"] == "http_responding" for r in db.get_latest_scan())


@pytest.mark.parametrize("exception,expected", [(TimeoutError(), "http_timeout")])
def test_request_errors_have_local_classification(exception, expected):
    session = MagicMock()
    context = AsyncMock()
    context.__aenter__.side_effect = exception
    session.head.return_value = context
    errors = []
    assert asyncio.run(
        https_ping("https://example.com", session=session, errors=errors)
    ) == (None, None, False)
    assert errors == [expected]


def test_csv_export_preserves_status_and_missing_timings(tmp_path):
    import csv

    from src.reporter import export_results

    def result(domain, latency, responding, status):
        return PingResult(
            MirrorConfig(domain, f"https://{domain}"),
            https_latency_ms=latency,
            is_up=responding,
            reachability=status,
        )

    export_results(
        [
            result("blocked.example", 1, False, "blocked_or_challenged"),
            result("zero.example", 0, True, "http_responding"),
            result("slow.example", 20, True, "http_responding"),
        ],
        {},
        fmt="csv",
        output_dir=str(tmp_path),
    )
    with next(tmp_path.glob("*.csv")).open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [row["Domain"] for row in rows] == [
        "zero.example",
        "slow.example",
        "blocked.example",
    ]
    assert rows[-1]["Status"] == "blocked_or_challenged"
    assert rows[-1]["Best_ms"] == ""
    assert rows[0]["Best_ms"] == "0"
