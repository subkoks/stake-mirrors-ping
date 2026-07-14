"""Tests for GeoIP resolution and the shared _apply_geoip helper."""

import asyncio
from unittest.mock import patch

from src.dns_resolver import _apply_geoip, enrich_with_geoip, geoip_lookup
from src.models import MirrorConfig, PingResult


class TestApplyGeoip:
    def test_applies_ipquery_shape(self) -> None:
        """ipquery.io nests coordinates under location.latitude/longitude."""
        r = PingResult(mirror=MirrorConfig(domain="x", url="https://x"))
        geo = {
            "location": {
                "country": "United States",
                "city": "Mountain View",
                "latitude": 37.4,
                "longitude": -122.07,
            }
        }
        _apply_geoip(r, geo)
        assert r.server_country == "United States"
        assert r.server_city == "Mountain View"
        assert r.server_location == "Mountain View, United States"
        assert r.server_lat == 37.4
        assert r.server_lon == -122.07

    def test_no_location_is_noop(self) -> None:
        r = PingResult(mirror=MirrorConfig(domain="x", url="https://x"))
        _apply_geoip(r, {})
        assert r.server_location is None
        assert r.server_lat is None


class TestGeoipLookup:
    def test_invalid_ip_returns_empty_without_network(self) -> None:
        with patch("src.dns_resolver.aiohttp.ClientSession") as sess_cls:
            assert asyncio.run(geoip_lookup("not-an-ip")) == {}
            sess_cls.assert_not_called()

    def test_enrich_with_geoip_populates(self) -> None:
        results = [
            PingResult(
                mirror=MirrorConfig(domain="x", url="https://x"),
                ip_address="1.2.3.4",
            )
        ]
        fake_geo = {
            "location": {
                "country": "DE",
                "city": "Frankfurt",
                "latitude": 50.1,
                "longitude": 8.7,
            }
        }
        with patch("src.dns_resolver.geoip_lookup", return_value=fake_geo):
            out = asyncio.run(enrich_with_geoip(results, concurrency=1))
        assert out is results
        assert results[0].server_city == "Frankfurt"
