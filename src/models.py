from dataclasses import dataclass, field


@dataclass
class MirrorConfig:
    domain: str
    url: str
    # Whether this mirror is allowed to receive the authenticated Stake session
    # token (x-access-token / session cookie). Defaults to False so a live
    # real-money token is never broadcast to an unverified/squatted mirror.
    trusted: bool = False


@dataclass
class PingResult:
    mirror: MirrorConfig
    tcp_latency_ms: float | None = None
    https_latency_ms: float | None = None
    api_latency_ms: float | None = None
    bet_latency_ms: float | None = None
    dns_resolve_ms: float | None = None
    ip_address: str | None = None
    server_location: str | None = None
    server_country: str | None = None
    server_city: str | None = None
    server_lat: float | None = None
    server_lon: float | None = None
    is_up: bool = False
    ssl_valid: bool = False
    http_status: int | None = None
    error: str | None = None

    @property
    def avg_latency_ms(self) -> float | None:
        latencies = [
            v
            for v in [self.tcp_latency_ms, self.https_latency_ms, self.api_latency_ms]
            if v is not None
        ]
        return sum(latencies) / len(latencies) if latencies else None

    @property
    def best_latency_ms(self) -> float | None:
        latencies = [
            v
            for v in [self.tcp_latency_ms, self.https_latency_ms, self.api_latency_ms]
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
