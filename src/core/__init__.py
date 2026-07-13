"""Core modules for Stake Mirrors Ping — CLI-independent API."""

from .orchestrator import (
    OrchestratorConfig,
    ScanResult,
    load_config,
    parse_mirrors,
    resolve_trusted_domains,
    run_scan,
)
from .serializers import (
    HistoryStatsSchema,
    MirrorResultSchema,
    ScanResultSchema,
    ScanSummarySchema,
    VPNRecommendationSchema,
)

__all__ = [
    "OrchestratorConfig",
    "ScanResult",
    "load_config",
    "parse_mirrors",
    "resolve_trusted_domains",
    "run_scan",
    "HistoryStatsSchema",
    "MirrorResultSchema",
    "ScanResultSchema",
    "ScanSummarySchema",
    "VPNRecommendationSchema",
]
