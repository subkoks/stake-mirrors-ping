#!/usr/bin/env python3
"""Pydantic serializers for JSON export shape and API contracts."""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class MirrorResultSchema(BaseModel):
    """Serialized mirror ping result for JSON export."""

    domain: str
    url: str
    is_up: bool
    ip_address: str | None = None
    server_location: str | None = None
    server_country: str | None = None
    server_city: str | None = None
    server_lat: float | None = None
    server_lon: float | None = None
    dns_ms: float | None = None
    tcp_ms: float | None = None
    https_ms: float | None = None
    api_ms: float | None = None
    bet_ms: float | None = None
    best_ms: float | None = None
    ssl_valid: bool = False
    http_status: int | None = None
    error: str | None = None
    trusted: bool = False


class HistoryStatsSchema(BaseModel):
    """Serialized uptime and latency stats for a mirror."""

    domain: str
    uptime_pct: float
    total_checks: int
    avg_best_ms: float | None = None
    min_best_ms: float | None = None
    max_best_ms: float | None = None
    avg_tcp_ms: float | None = None
    avg_api_ms: float | None = None


class VPNRecommendationSchema(BaseModel):
    """Serialized VPN recommendation for a mirror."""

    mirror_domain: str
    vpn_hostname: str
    vpn_country: str
    vpn_city: str
    distance_km: float
    mirror_latency_ms: float
    estimated_total_ms: float


class ScanSummarySchema(BaseModel):
    """Summary of a scan run."""

    scan_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    total_mirrors: int
    up_mirrors: int
    fastest_mirror: str | None = None
    fastest_latency_ms: float | None = None


class ScanResultSchema(BaseModel):
    """Complete scan result with mirrors, recommendations, and metadata."""

    scan: ScanSummarySchema
    mirrors: list[MirrorResultSchema]
    vpn_recommendations: list[VPNRecommendationSchema]

    def model_dump_json(self, **kwargs) -> str:
        """Export to JSON string."""
        return super().model_dump_json(indent=2, **kwargs)
