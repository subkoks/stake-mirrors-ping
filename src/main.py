#!/usr/bin/env python3
"""Stake Mirrors Ping — Find the fastest Stake.com mirror + optimal NordVPN region."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)

from .models import MirrorConfig
from .pinger import ping_all_mirrors
from .dns_resolver import enrich_with_geoip
from .nordvpn import get_vpn_recommendations
from .stake_api import enrich_with_api_tests
from .reporter import print_results_table, print_vpn_recommendations, export_results
from .dashboard import run_live_dashboard
from .history import save_results, get_uptime_stats, get_scan_count
from .log import setup_logging

console = Console()


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        console.print(f"[red]Config file not found: {config_path}[/]")
        sys.exit(1)
    with open(path) as f:
        return yaml.safe_load(f)


def resolve_trusted_domains(config: dict) -> set[str]:
    """Domains allowed to receive the authenticated session token.

    Union of ``settings.trusted_api_domains`` in config and the
    ``STAKE_TRUSTED_DOMAINS`` env var (comma-separated). Empty by default so
    the live token is never sent anywhere the user has not explicitly verified.
    """
    settings = config.get("settings", {})
    trusted: set[str] = {
        str(d).strip().lower()
        for d in settings.get("trusted_api_domains", [])
        if str(d).strip()
    }
    env_value = os.getenv("STAKE_TRUSTED_DOMAINS", "")
    trusted |= {d.strip().lower() for d in env_value.split(",") if d.strip()}
    return trusted


def parse_mirrors(config: dict) -> list[MirrorConfig]:
    """Parse mirror list from config, flagging trusted (token-eligible) hosts."""
    trusted_domains = resolve_trusted_domains(config)
    return [
        MirrorConfig(
            domain=m["domain"],
            url=m["url"],
            trusted=m["domain"].strip().lower() in trusted_domains,
        )
        for m in config.get("mirrors", [])
    ]


async def run(args: argparse.Namespace) -> None:
    """Main async runner."""
    # Load config
    config = load_config(args.config)
    mirrors = parse_mirrors(config)
    settings = config.get("settings", {})
    nordvpn_config = config.get("nordvpn", {})

    rounds = args.rounds or settings.get("ping_rounds", 3)
    timeout = args.timeout or settings.get("timeout_seconds", 10)
    concurrency = settings.get("concurrent_limit", 16)

    session_token = os.getenv("STAKE_SESSION_TOKEN")

    # --history: show stats and exit
    if args.history:
        from rich.table import Table

        stats = get_uptime_stats()
        if not stats:
            console.print("[yellow]No history data yet. Run a scan first.[/]")
            return
        table = Table(
            title=f"Mirror Uptime Stats (last 24h) — {get_scan_count()} scans",
            show_lines=True,
        )
        table.add_column("Mirror", style="bold")
        table.add_column("Uptime", justify="right")
        table.add_column("Avg Best", justify="right")
        table.add_column("Min Best", justify="right")
        table.add_column("Max Best", justify="right")
        table.add_column("Avg TCP", justify="right")
        table.add_column("Avg API", justify="right")
        table.add_column("Checks", justify="right", style="dim")
        for domain, s in stats.items():
            uptime_color = (
                "green"
                if s["uptime_pct"] >= 99
                else "yellow"
                if s["uptime_pct"] >= 90
                else "red"
            )
            table.add_row(
                domain,
                f"[{uptime_color}]{s['uptime_pct']}%[/]",
                f"{s['avg_best_ms'] or '—'}ms",
                f"{s['min_best_ms'] or '—'}ms",
                f"{s['max_best_ms'] or '—'}ms",
                f"{s['avg_tcp_ms'] or '—'}ms",
                f"{s['avg_api_ms'] or '—'}ms",
                str(s["total_checks"]),
            )
        console.print(table)
        return

    # Live dashboard — skip one-shot flow entirely
    if args.live:
        await run_live_dashboard(
            mirrors,
            interval=args.live,
            rounds=rounds,
            timeout=timeout,
            concurrency=concurrency,
            skip_geoip=args.skip_geoip,
            api=args.api,
            session_token=session_token,
        )
        return

    console.print(
        Panel(
            f"[bold cyan]Stake Mirrors Ping[/]\n"
            f"Mirrors: {len(mirrors)} | Rounds: {rounds} | Timeout: {timeout}s\n"
            f"API Mode: {'[green]ON[/]' if args.api else '[dim]OFF[/]'} | "
            f"Bet Test: {'[green]ON[/]' if args.benchmark_bets else '[dim]OFF[/]'}",
            border_style="cyan",
        )
    )

    # Step 1: Ping all mirrors
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Pinging all mirrors...", total=None)
        results = await ping_all_mirrors(
            mirrors, rounds=rounds, timeout=timeout, concurrency=concurrency
        )
        progress.update(task, completed=True, description="[green]Pinging complete!")

    up_count = sum(1 for r in results if r.is_up)
    console.print(f"[dim]{up_count}/{len(results)} mirrors responding[/]")

    # Step 2: GeoIP enrichment
    if not args.skip_geoip:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Resolving server locations...", total=None)
            results = await enrich_with_geoip(results)
            progress.update(task, completed=True, description="[green]GeoIP complete!")

    # Step 3: Stake API tests (if token provided)
    if args.api and session_token:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Testing API latency...", total=None)
            results = await enrich_with_api_tests(
                results,
                session_token,
                rounds=rounds,
                run_bets=args.benchmark_bets,
            )
            progress.update(
                task, completed=True, description="[green]API tests complete!"
            )
    elif args.api and not session_token:
        console.print(
            "[yellow]⚠ --api flag set but STAKE_SESSION_TOKEN not found in .env[/]"
        )

    # Save to history
    if not args.no_history:
        saved = save_results(results)
        console.print(
            f"[dim]Saved {saved} results to history.db ({get_scan_count()} total scans)[/]"
        )

    # Step 4: Print results
    print_results_table(results)

    # Step 5: NordVPN recommendations
    if not args.skip_vpn:
        target_countries = nordvpn_config.get("target_regions", [])
        if target_countries:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Fetching NordVPN servers...", total=None)
                recommendations = await get_vpn_recommendations(
                    results, target_countries
                )
                progress.update(
                    task, completed=True, description="[green]VPN analysis complete!"
                )

            print_vpn_recommendations(recommendations)
        else:
            recommendations = {}
    else:
        recommendations = {}

    # Step 6: Export
    if args.export:
        export_results(
            results, recommendations, fmt=args.export, output_dir=args.output_dir
        )

    # Continuous mode (legacy)
    if args.watch:
        console.print(
            f"\n[dim]Refreshing every {args.watch} seconds... (Ctrl+C to stop)[/]"
        )
        try:
            while True:
                await asyncio.sleep(args.watch)
                console.clear()
                results = await ping_all_mirrors(
                    mirrors, rounds=rounds, timeout=timeout, concurrency=concurrency
                )
                if not args.skip_geoip:
                    results = await enrich_with_geoip(results)
                if args.api and session_token:
                    results = await enrich_with_api_tests(
                        results, session_token, rounds=rounds, run_bets=False
                    )
                print_results_table(
                    results,
                    title=f"Stake Mirror Ping — {__import__('datetime').datetime.now().strftime('%H:%M:%S')}",
                )
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped.[/]")


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
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
