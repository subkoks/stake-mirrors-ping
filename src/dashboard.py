"""Live dashboard for continuous mirror monitoring using rich.live."""

import asyncio
from datetime import datetime

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from .dns_resolver import enrich_with_geoip
from .models import MirrorConfig, PingResult
from .pinger import ping_all_mirrors
from .reporter import fmt_ms, latency_color
from .stake_api import enrich_with_api_tests

console = Console()


def _build_header(cycle: int, interval: int, up: int, total: int) -> Panel:
    """Build the dashboard header panel."""
    now = datetime.now().strftime("%H:%M:%S")
    return Panel(
        f"[bold cyan]Stake Mirrors Live Dashboard[/]  │  "
        f"[dim]{now}[/]  │  "
        f"Cycle [bold]{cycle}[/]  │  "
        f"Refresh: {interval}s  │  "
        f"[green]{up}[/]/{total} mirrors up  │  "
        f"[dim]Ctrl+C to stop[/]",
        border_style="cyan",
        padding=(0, 1),
    )


def _build_mirror_table(results: list[PingResult], show_api: bool = False) -> Table:
    """Build the mirror results table."""
    sorted_results = sorted(
        results,
        key=lambda r: r.best_latency_ms if r.best_latency_ms is not None else 99999,
    )

    table = Table(show_lines=True, expand=True, title_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Mirror", style="bold", min_width=14)
    table.add_column("Status", width=6)
    table.add_column("IP", style="dim", min_width=12)
    table.add_column("Location", style="cyan", min_width=10)
    table.add_column("TCP", justify="right", min_width=7)
    table.add_column("HTTPS", justify="right", min_width=7)
    if show_api:
        table.add_column("API", justify="right", min_width=7)
    table.add_column("Best", justify="right", style="bold", min_width=7)
    table.add_column("Trend", justify="center", width=5)

    for i, r in enumerate(sorted_results, 1):
        status = "[green]✓ UP[/]" if r.is_up else "[red]✗ DN[/]"
        ssl_icon = "🔒" if r.ssl_valid else "⚠️"

        # Simple trend indicator based on TCP vs HTTPS spread
        trend = ""
        if r.tcp_latency_ms and r.best_latency_ms:
            if r.best_latency_ms < 30:
                trend = "[green]●[/]"
            elif r.best_latency_ms < 50:
                trend = "[yellow]●[/]"
            else:
                trend = "[red]●[/]"

        row = [
            str(i),
            f"{r.mirror.domain} {ssl_icon}",
            status,
            r.ip_address or "—",
            r.server_location or "—",
            f"[{latency_color(r.tcp_latency_ms)}]{fmt_ms(r.tcp_latency_ms)}[/]",
            f"[{latency_color(r.https_latency_ms)}]{fmt_ms(r.https_latency_ms)}[/]",
        ]
        if show_api:
            row.append(
                f"[{latency_color(r.api_latency_ms)}]{fmt_ms(r.api_latency_ms)}[/]"
            )
        row.extend(
            [
                f"[{latency_color(r.best_latency_ms)}]{fmt_ms(r.best_latency_ms)}[/]",
                trend,
            ]
        )
        table.add_row(*row)

    return table


def _build_footer(results: list[PingResult]) -> Panel:
    """Build the footer with best mirror info."""
    sorted_up = [r for r in results if r.is_up and r.best_latency_ms is not None]
    if not sorted_up:
        return Panel("[red]No mirrors responding[/]", border_style="red")

    sorted_up.sort(key=lambda r: r.best_latency_ms or 999)
    best = sorted_up[0]
    second = sorted_up[1] if len(sorted_up) > 1 else None

    text = (
        f"[bold green]🏆 {best.mirror.domain}[/] — "
        f"{fmt_ms(best.best_latency_ms)} "
        f"[dim]({best.server_location or '?'})[/]"
    )
    if second:
        text += (
            f"   │   [dim]Runner-up:[/] {second.mirror.domain} — "
            f"{fmt_ms(second.best_latency_ms)}"
        )

    return Panel(text, title="Fastest Mirror", border_style="green", padding=(0, 1))


def _build_layout(
    results: list[PingResult],
    cycle: int,
    interval: int,
    show_api: bool,
) -> Layout:
    """Build the full dashboard layout."""
    up_count = sum(1 for r in results if r.is_up)
    total = len(results)

    layout = Layout()
    layout.split_column(
        Layout(_build_header(cycle, interval, up_count, total), name="header", size=3),
        Layout(_build_mirror_table(results, show_api=show_api), name="table"),
        Layout(_build_footer(results), name="footer", size=3),
    )
    return layout


async def run_live_dashboard(
    mirrors: list[MirrorConfig],
    interval: int = 30,
    rounds: int = 3,
    timeout: float = 10.0,
    concurrency: int = 16,
    skip_geoip: bool = False,
    api: bool = False,
    session_token: str | None = None,
) -> None:
    """Run the live auto-refreshing dashboard."""
    cycle = 0

    # Initial run
    console.print("[dim]Running initial scan...[/]")
    results = await ping_all_mirrors(
        mirrors, rounds=rounds, timeout=timeout, concurrency=concurrency
    )
    if not skip_geoip:
        results = await enrich_with_geoip(results)
    if api and session_token:
        results = await enrich_with_api_tests(results, session_token, rounds=rounds)
    cycle += 1

    layout = _build_layout(results, cycle, interval, show_api=api)

    try:
        with Live(layout, console=console, refresh_per_second=1, screen=True) as live:
            while True:
                await asyncio.sleep(interval)
                cycle += 1

                # Re-ping all mirrors
                new_results = await ping_all_mirrors(
                    mirrors,
                    rounds=rounds,
                    timeout=timeout,
                    concurrency=concurrency,
                )
                # Carry over GeoIP from previous results to avoid rate limiting
                ip_to_geo = {
                    r.ip_address: (
                        r.server_location,
                        r.server_country,
                        r.server_city,
                        r.server_lat,
                        r.server_lon,
                    )
                    for r in results
                    if r.ip_address and r.server_location
                }
                for r in new_results:
                    if r.ip_address in ip_to_geo:
                        loc, country, city, lat, lon = ip_to_geo[r.ip_address]
                        r.server_location = loc
                        r.server_country = country
                        r.server_city = city
                        r.server_lat = lat
                        r.server_lon = lon
                    elif (
                        not skip_geoip
                        and r.ip_address
                        and r.ip_address not in ip_to_geo
                    ):
                        # New IP, resolve it
                        from .dns_resolver import geoip_lookup

                        geo = await geoip_lookup(r.ip_address)
                        if geo.get("status") == "success":
                            r.server_country = geo.get("country", "Unknown")
                            r.server_city = geo.get("city", "Unknown")
                            r.server_location = (
                                f"{geo.get('city', '?')}, {geo.get('country', '?')}"
                            )
                            r.server_lat = geo.get("lat")
                            r.server_lon = geo.get("lon")

                if api and session_token:
                    new_results = await enrich_with_api_tests(
                        new_results,
                        session_token,
                        rounds=rounds,
                        run_bets=False,
                    )

                results = new_results
                live.update(_build_layout(results, cycle, interval, show_api=api))

    except KeyboardInterrupt:
        pass

    console.print("\n[dim]Dashboard stopped.[/]")
