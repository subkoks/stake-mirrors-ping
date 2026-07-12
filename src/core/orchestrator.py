#!/usr/bin/env python3
"""Orchestrator for Stake Mirrors Ping — prepares inputs and delegates to core services."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from ..dashboard import run_live_dashboard
from ..dns_resolver import enrich_with_geoip
from ..history import get_scan_count, get_uptime_stats, save_results
from ..models import MirrorConfig
from ..nordvpn import get_vpn_recommendations
from ..pinger import ping_all_mirrors
from ..reporter import export_results, print_results_table, print_vpn_recommendations
from ..stake_api import enrich_with_api_tests

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


async def orchestrate(args: argparse.Namespace) -> None:
    """Top-level async orchestration for one-shot scan or live dashboard."""
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
