#!/usr/bin/env python3
"""Pydantic serializers for JSON export shape and API contracts."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class MirrorResultSchema(BaseModel):
    """Serialized mirror ping result for JSON export."""

    domain: str
    url: str
    is_up: bool
    ip_address: Optional[str] = None
    server_location: Optional[str] = None
    server_country: Optional[str] = None
    server_city: Optional[str] = None
    server_lat: Optional[float] = None
    server_lon: Optional[float] = None
    dns_ms: Optional[float] = None
    tcp_ms: Optional[float] = None
    https_ms: Optional[float] = None
    api_ms: Optional[float] = None
    bet_ms: Optional[float] = None
    best_ms: Optional[float] = None
    ssl_valid: bool = False
    http_status: Optional[int] = None
    error: Optional[str] = None
    trusted: bool = False


class HistoryStatsSchema(BaseModel):
    """Serialized uptime and latency stats for a mirror."""

    domain: str
    uptime_pct: float
    total_checks: int
    avg_best_ms: Optional[float] = None
    min_best_ms: Optional[float] = None
    max_best_ms: Optional[float] = None
    avg_tcp_ms: Optional[float] = None
    avg_api_ms: Optional[float] = None


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
    fastest_mirror: Optional[str] = None
    fastest_latency_ms: Optional[float] = None


class ScanResultSchema(BaseModel):
    """Complete scan result with mirrors, recommendations, and metadata."""

    scan: ScanSummarySchema
    mirrors: list[MirrorResultSchema]
    vpn_recommendations: list[VPNRecommendationSchema]

    def model_dump_json(self, **kwargs) -> str:
        """Export to JSON string."""
        return super().model_dump_json(indent=2, **kwargs)
