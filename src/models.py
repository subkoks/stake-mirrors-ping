from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MirrorConfig:
    domain: str
    url: str


@dataclass
class PingResult:
    mirror: MirrorConfig
    tcp_latency_ms: Optional[float] = None
    https_latency_ms: Optional[float] = None
    api_latency_ms: Optional[float] = None
    ws_latency_ms: Optional[float] = None
    bet_latency_ms: Optional[float] = None
    dns_resolve_ms: Optional[float] = None
    ip_address: Optional[str] = None
    server_location: Optional[str] = None
    server_country: Optional[str] = None
    server_city: Optional[str] = None
    server_lat: Optional[float] = None
    server_lon: Optional[float] = None
    is_up: bool = False
    ssl_valid: bool = False
    http_status: Optional[int] = None
    error: Optional[str] = None

    @property
    def avg_latency_ms(self) -> Optional[float]:
        latencies = [
            v for v in [self.tcp_latency_ms, self.https_latency_ms, self.api_latency_ms]
            if v is not None
        ]
        return sum(latencies) / len(latencies) if latencies else None

    @property
    def best_latency_ms(self) -> Optional[float]:
        latencies = [
            v for v in [
                self.tcp_latency_ms, self.https_latency_ms,
                self.api_latency_ms, self.ws_latency_ms
            ]
            if v is not None
        ]
        return min(latencies) if latencies else None


@dataclass
class NordVPNServer:
    name: str
    hostname: str
    country: str
    city: str
    lat: float
    lon: float
    load: int
    features: list = field(default_factory=list)


@dataclass
class VPNRecommendation:
    mirror: MirrorConfig
    vpn_server: NordVPNServer
    estimated_latency_ms: float
    distance_km: float
    mirror_latency_ms: float
