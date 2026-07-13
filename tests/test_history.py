"""Tests for SQLite history module."""

from pathlib import Path

import pytest

from src.history import (
    get_domain_history,
    get_latest_scan,
    get_scan_count,
    get_uptime_stats,
    save_results,
)
from src.models import MirrorConfig, PingResult


@pytest.fixture
def tmp_db(tmp_path: Path) -> str:
    """Return path to a temporary SQLite database."""
    return str(tmp_path / "test_history.db")


@pytest.fixture
def sample_results() -> list[PingResult]:
    mirrors = [
        MirrorConfig(domain="stake.com", url="https://stake.com"),
        MirrorConfig(domain="stake.bet", url="https://stake.bet"),
    ]
    return [
        PingResult(
            mirror=mirrors[0],
            is_up=True,
            tcp_latency_ms=25.0,
            https_latency_ms=50.0,
            ip_address="1.2.3.4",
            ssl_valid=True,
            http_status=200,
        ),
        PingResult(
            mirror=mirrors[1],
            is_up=False,
            error="DNS resolution failed",
        ),
    ]


class TestSaveResults:
    def test_saves_and_returns_count(
        self, tmp_db: str, sample_results: list[PingResult]
    ) -> None:
        count = save_results(sample_results, db_path=tmp_db)
        assert count == 2

    def test_multiple_saves_accumulate(
        self, tmp_db: str, sample_results: list[PingResult]
    ) -> None:
        save_results(sample_results, db_path=tmp_db)
        save_results(sample_results, db_path=tmp_db)
        assert get_scan_count(db_path=tmp_db) == 2


class TestGetDomainHistory:
    def test_returns_history_for_domain(
        self, tmp_db: str, sample_results: list[PingResult]
    ) -> None:
        save_results(sample_results, db_path=tmp_db)
        history = get_domain_history("stake.com", db_path=tmp_db)
        assert len(history) == 1
        assert history[0]["domain"] == "stake.com"
        assert history[0]["is_up"] == 1

    def test_returns_empty_for_unknown_domain(
        self, tmp_db: str, sample_results: list[PingResult]
    ) -> None:
        save_results(sample_results, db_path=tmp_db)
        history = get_domain_history("unknown.com", db_path=tmp_db)
        assert history == []

    def test_respects_limit(
        self, tmp_db: str, sample_results: list[PingResult]
    ) -> None:
        for _ in range(5):
            save_results(sample_results, db_path=tmp_db)
        history = get_domain_history("stake.com", limit=3, db_path=tmp_db)
        assert len(history) == 3


class TestGetLatestScan:
    def test_returns_latest_scan(
        self, tmp_db: str, sample_results: list[PingResult]
    ) -> None:
        save_results(sample_results, db_path=tmp_db)
        latest = get_latest_scan(db_path=tmp_db)
        assert len(latest) == 2

    def test_returns_empty_when_no_data(self, tmp_db: str) -> None:
        latest = get_latest_scan(db_path=tmp_db)
        assert latest == []


class TestGetUptimeStats:
    def test_returns_stats(self, tmp_db: str, sample_results: list[PingResult]) -> None:
        save_results(sample_results, db_path=tmp_db)
        stats = get_uptime_stats(db_path=tmp_db)
        assert "stake.com" in stats
        assert "stake.bet" in stats
        assert stats["stake.com"]["uptime_pct"] == 100.0
        assert stats["stake.bet"]["uptime_pct"] == 0.0

    def test_returns_empty_when_no_data(self, tmp_db: str) -> None:
        stats = get_uptime_stats(db_path=tmp_db)
        assert stats == {}


class TestGetScanCount:
    def test_counts_distinct_scans(
        self, tmp_db: str, sample_results: list[PingResult]
    ) -> None:
        assert get_scan_count(db_path=tmp_db) == 0
        save_results(sample_results, db_path=tmp_db)
        assert get_scan_count(db_path=tmp_db) == 1
