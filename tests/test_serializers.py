#!/usr/bin/env python3
"""Tests for Pydantic serializers."""

import json

from src.core.serializers import (
    HistoryStatsSchema,
    MirrorResultSchema,
    ScanResultSchema,
    ScanSummarySchema,
    VPNRecommendationSchema,
)


def test_mirror_result_schema():
    """Test MirrorResultSchema validation and serialization."""
    schema = MirrorResultSchema(
        domain="stake.bet",
        url="https://stake.bet",
        is_up=True,
        ip_address="1.2.3.4",
        server_location="London, UK",
        server_country="UK",
        server_city="London",
        server_lat=51.5,
        server_lon=-0.1,
        dns_ms=5.0,
        tcp_ms=12.3,
        https_ms=45.6,
        api_ms=89.1,
        bet_ms=150.0,
        best_ms=12.3,
        ssl_valid=True,
        http_status=200,
        error=None,
        trusted=True,
    )

    # Test model_dump
    data = schema.model_dump()
    assert data["domain"] == "stake.bet"
    assert data["is_up"] is True
    assert data["best_ms"] == 12.3

    # Test JSON round-trip
    json_str = schema.model_dump_json()
    parsed = json.loads(json_str)
    assert parsed["domain"] == "stake.bet"
    assert parsed["best_ms"] == 12.3


def test_mirror_result_schema_minimal():
    """Test MirrorResultSchema with minimal required fields."""
    schema = MirrorResultSchema(
        domain="stake.ac",
        url="https://stake.ac",
        is_up=False,
    )

    assert schema.domain == "stake.ac"
    assert schema.is_up is False
    assert schema.ip_address is None


def test_history_stats_schema():
    """Test HistoryStatsSchema validation."""
    schema = HistoryStatsSchema(
        domain="stake.bet",
        uptime_pct=99.5,
        total_checks=100,
        avg_best_ms=12.3,
        min_best_ms=10.0,
        max_best_ms=20.0,
        avg_tcp_ms=15.0,
        avg_api_ms=90.0,
    )

    assert schema.domain == "stake.bet"
    assert schema.uptime_pct == 99.5
    assert schema.total_checks == 100


def test_vpn_recommendation_schema():
    """Test VPNRecommendationSchema validation."""
    schema = VPNRecommendationSchema(
        mirror_domain="stake.bet",
        vpn_hostname="uk123.nordvpn.com",
        vpn_country="United Kingdom",
        vpn_city="London",
        distance_km=500.0,
        mirror_latency_ms=12.3,
        estimated_total_ms=27.3,
    )

    assert schema.mirror_domain == "stake.bet"
    assert schema.vpn_city == "London"
    assert schema.estimated_total_ms == 27.3


def test_scan_summary_schema():
    """Test ScanSummarySchema with auto-generated fields."""
    schema = ScanSummarySchema(
        total_mirrors=16,
        up_mirrors=15,
        fastest_mirror="stake.bet",
        fastest_latency_ms=12.3,
    )

    assert schema.total_mirrors == 16
    assert schema.up_mirrors == 15
    assert schema.scan_id  # Should be auto-generated UUID
    assert schema.timestamp  # Should be auto-generated ISO timestamp


def test_scan_result_schema():
    """Test complete ScanResultSchema."""
    mirrors = [
        MirrorResultSchema(
            domain="stake.bet",
            url="https://stake.bet",
            is_up=True,
            best_ms=12.3,
        )
    ]
    vpns = [
        VPNRecommendationSchema(
            mirror_domain="stake.bet",
            vpn_hostname="uk123.nordvpn.com",
            vpn_country="UK",
            vpn_city="London",
            distance_km=500.0,
            mirror_latency_ms=12.3,
            estimated_total_ms=27.3,
        )
    ]
    summary = ScanSummarySchema(
        total_mirrors=1,
        up_mirrors=1,
        fastest_mirror="stake.bet",
        fastest_latency_ms=12.3,
    )

    schema = ScanResultSchema(
        scan=summary,
        mirrors=mirrors,
        vpn_recommendations=vpns,
    )

    # Test JSON export
    json_str = schema.model_dump_json()
    parsed = json.loads(json_str)

    assert "scan" in parsed
    assert "mirrors" in parsed
    assert "vpn_recommendations" in parsed
    assert parsed["scan"]["total_mirrors"] == 1
    assert len(parsed["mirrors"]) == 1
    assert parsed["mirrors"][0]["domain"] == "stake.bet"


def test_scan_result_schema_empty():
    """Test ScanResultSchema with empty results."""
    summary = ScanSummarySchema(
        total_mirrors=0,
        up_mirrors=0,
    )

    schema = ScanResultSchema(
        scan=summary,
        mirrors=[],
        vpn_recommendations=[],
    )

    assert schema.scan.total_mirrors == 0
    assert len(schema.mirrors) == 0
    assert len(schema.vpn_recommendations) == 0
