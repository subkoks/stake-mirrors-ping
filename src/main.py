#!/usr/bin/env python3
"""Stake Mirrors Ping — Find the fastest Stake.com mirror + optimal NordVPN region."""

import argparse
import asyncio

from dotenv import load_dotenv

from .core.orchestrator import orchestrate
from .log import setup_logging


def main() -> None:
    """CLI entry point."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Stake Mirrors Ping — Find the fastest mirror + VPN combo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main                          # Basic ping test
  python -m src.main --api                    # Include API latency tests
  python -m src.main --api --benchmark-bets   # Include $0 bet latency
  python -m src.main --export json            # Export results to JSON
  python -m src.main --export csv             # Export results to CSV
  python -m src.main --watch 60               # Refresh every 60 seconds
  python -m src.main --skip-vpn               # Skip NordVPN recommendations
  python -m src.main --rounds 5 --timeout 15  # Custom rounds and timeout
        """,
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument(
        "--rounds", type=int, help="Number of ping rounds (default: from config)"
    )
    parser.add_argument(
        "--timeout", type=float, help="Timeout in seconds (default: from config)"
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Enable Stake API latency tests (requires STAKE_SESSION_TOKEN)",
    )
    parser.add_argument(
        "--benchmark-bets", action="store_true", help="Enable $0 Dice bet latency test"
    )
    parser.add_argument("--skip-geoip", action="store_true", help="Skip GeoIP lookups")
    parser.add_argument(
        "--skip-vpn", action="store_true", help="Skip NordVPN recommendations"
    )
    parser.add_argument(
        "--export", choices=["json", "csv"], help="Export results to file"
    )
    parser.add_argument(
        "--output-dir", default="results", help="Output directory for exports"
    )
    parser.add_argument(
        "--watch",
        type=int,
        metavar="SECONDS",
        help="Continuous monitoring (legacy, use --live)",
    )
    parser.add_argument(
        "--live", type=int, metavar="SECONDS", help="Live dashboard with auto-refresh"
    )
    parser.add_argument(
        "--no-history", action="store_true", help="Don't save results to history.db"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--history", action="store_true", help="Show uptime stats from history.db"
    )

    args = parser.parse_args()
    setup_logging(verbose=getattr(args, "verbose", False))
    asyncio.run(orchestrate(args))


if __name__ == "__main__":
    main()
