"""Tests for NordVPN utility functions."""

from src.models import MirrorConfig, NordVPNServer, PingResult
from src.nordvpn import estimate_vpn_latency, find_best_vpn_for_mirror, haversine_km


class TestHaversine:
    def test_same_point_is_zero(self) -> None:
        assert haversine_km(50.0, 8.0, 50.0, 8.0) == 0.0

    def test_known_distance(self) -> None:
        # Frankfurt (50.1, 8.7) to Amsterdam (52.4, 4.9) ~ 365 km
        dist = haversine_km(50.1, 8.7, 52.4, 4.9)
        assert 350 < dist < 400

    def test_long_distance(self) -> None:
        # London (51.5, -0.1) to New York (40.7, -74.0) ~ 5570 km
        dist = haversine_km(51.5, -0.1, 40.7, -74.0)
        assert 5500 < dist < 5700

    def test_symmetric(self) -> None:
        d1 = haversine_km(50.0, 8.0, 52.0, 4.0)
        d2 = haversine_km(52.0, 4.0, 50.0, 8.0)
        assert abs(d1 - d2) < 0.01


class TestEstimateVPNLatency:
    def test_zero_distance_low_load(self) -> None:
        latency = estimate_vpn_latency(0.0, 0)
        assert latency == 15.0  # base overhead only

    def test_distance_increases_latency(self) -> None:
        near = estimate_vpn_latency(100.0, 10)
        far = estimate_vpn_latency(5000.0, 10)
        assert far > near

    def test_load_increases_latency(self) -> None:
        low = estimate_vpn_latency(1000.0, 10)
        high = estimate_vpn_latency(1000.0, 90)
        assert high > low

    def test_result_is_rounded(self) -> None:
        latency = estimate_vpn_latency(123.456, 33)
        assert isinstance(latency, float)
        # Check it has at most 2 decimal places
        assert latency == round(latency, 2)


class TestFindBestVPNForMirror:
    def test_returns_empty_without_geo(self) -> None:
        m = MirrorConfig(domain="stake.com", url="https://stake.com")
        r = PingResult(mirror=m, is_up=True)
        servers = [
            NordVPNServer(
                "DE#1", "de1.nordvpn.com", "Germany", "Frankfurt", 50.1, 8.7, 20
            ),
        ]
        result = find_best_vpn_for_mirror(r, servers)
        assert result == []

    def test_returns_sorted_recommendations(self) -> None:
        m = MirrorConfig(domain="stake.com", url="https://stake.com")
        r = PingResult(
            mirror=m,
            is_up=True,
            tcp_latency_ms=30.0,
            server_lat=50.0,
            server_lon=8.0,
        )
        servers = [
            NordVPNServer(
                "DE#1", "de1.nordvpn.com", "Germany", "Frankfurt", 50.1, 8.7, 20
            ),
            NordVPNServer(
                "US#1", "us1.nordvpn.com", "USA", "New York", 40.7, -74.0, 50
            ),
        ]
        recs = find_best_vpn_for_mirror(r, servers, top_n=2)
        assert len(recs) == 2
        # Closer server (Frankfurt) should have lower estimated latency
        assert recs[0].vpn_server.country == "Germany"
        assert recs[0].estimated_latency_ms < recs[1].estimated_latency_ms

    def test_top_n_limits_results(self) -> None:
        m = MirrorConfig(domain="stake.com", url="https://stake.com")
        r = PingResult(
            mirror=m,
            is_up=True,
            tcp_latency_ms=30.0,
            server_lat=50.0,
            server_lon=8.0,
        )
        servers = [
            NordVPNServer(
                f"S{i}", f"s{i}.nordvpn.com", "DE", "Berlin", 52.5, 13.4, i * 10
            )
            for i in range(10)
        ]
        recs = find_best_vpn_for_mirror(r, servers, top_n=3)
        assert len(recs) == 3
