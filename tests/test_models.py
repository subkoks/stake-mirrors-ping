"""Tests for data models."""

import pytest
from src.models import MirrorConfig, PingResult, NordVPNServer, VPNRecommendation


class TestMirrorConfig:
    def test_creation(self) -> None:
        m = MirrorConfig(domain="stake.com", url="https://stake.com")
        assert m.domain == "stake.com"
        assert m.url == "https://stake.com"


class TestPingResult:
    def test_defaults(self) -> None:
        m = MirrorConfig(domain="stake.com", url="https://stake.com")
        r = PingResult(mirror=m)
        assert r.is_up is False
        assert r.tcp_latency_ms is None
        assert r.https_latency_ms is None
        assert r.api_latency_ms is None
        assert r.error is None

    def test_avg_latency_all_set(self) -> None:
        m = MirrorConfig(domain="stake.com", url="https://stake.com")
        r = PingResult(mirror=m, tcp_latency_ms=10.0, https_latency_ms=20.0, api_latency_ms=30.0)
        assert r.avg_latency_ms == 20.0

    def test_avg_latency_partial(self) -> None:
        m = MirrorConfig(domain="stake.com", url="https://stake.com")
        r = PingResult(mirror=m, tcp_latency_ms=10.0, https_latency_ms=20.0)
        assert r.avg_latency_ms == 15.0

    def test_avg_latency_none_when_empty(self) -> None:
        m = MirrorConfig(domain="stake.com", url="https://stake.com")
        r = PingResult(mirror=m)
        assert r.avg_latency_ms is None

    def test_best_latency(self) -> None:
        m = MirrorConfig(domain="stake.com", url="https://stake.com")
        r = PingResult(mirror=m, tcp_latency_ms=10.0, https_latency_ms=20.0, api_latency_ms=5.0)
        assert r.best_latency_ms == 5.0

    def test_best_latency_single(self) -> None:
        m = MirrorConfig(domain="stake.com", url="https://stake.com")
        r = PingResult(mirror=m, tcp_latency_ms=42.0)
        assert r.best_latency_ms == 42.0

    def test_best_latency_none(self) -> None:
        m = MirrorConfig(domain="stake.com", url="https://stake.com")
        r = PingResult(mirror=m)
        assert r.best_latency_ms is None


class TestNordVPNServer:
    def test_creation(self) -> None:
        s = NordVPNServer(
            name="Germany #123",
            hostname="de123.nordvpn.com",
            country="Germany",
            city="Frankfurt",
            lat=50.1,
            lon=8.7,
            load=25,
        )
        assert s.country == "Germany"
        assert s.load == 25
        assert s.features == []


class TestVPNRecommendation:
    def test_creation(self) -> None:
        m = MirrorConfig(domain="stake.com", url="https://stake.com")
        s = NordVPNServer(
            name="DE#1", hostname="de1.nordvpn.com",
            country="Germany", city="Frankfurt",
            lat=50.1, lon=8.7, load=20,
        )
        rec = VPNRecommendation(
            mirror=m, vpn_server=s,
            estimated_latency_ms=45.0, distance_km=500.0,
            mirror_latency_ms=30.0,
        )
        assert rec.estimated_latency_ms == 45.0
        assert rec.distance_km == 500.0
