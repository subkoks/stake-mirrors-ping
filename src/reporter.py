import csv
import json
import os
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .models import PingResult, VPNRecommendation


console = Console()


def latency_color(ms: Optional[float]) -> str:
    """Return color based on latency value."""
    if ms is None:
        return "dim"
    if ms < 100:
        return "green"
    if ms < 200:
        return "yellow"
    if ms < 400:
        return "red"
    return "bold red"


def fmt_ms(ms: Optional[float]) -> str:
    """Format milliseconds for display."""
    if ms is None:
        return "—"
    return f"{ms:.1f}ms"


def print_results_table(results: list[PingResult], title: str = "Stake Mirror Ping Results") -> None:
    """Print a sorted Rich table of ping results."""
    # Sort by best latency (None values last)
    sorted_results = sorted(
        results,
        key=lambda r: r.best_latency_ms if r.best_latency_ms is not None else 99999,
    )

    table = Table(title=title, show_lines=True, title_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Mirror", style="bold")
    table.add_column("Status", width=6)
    table.add_column("IP", style="dim")
    table.add_column("Location", style="cyan")
    table.add_column("DNS", justify="right")
    table.add_column("TCP", justify="right")
    table.add_column("HTTPS", justify="right")
    table.add_column("API", justify="right")
    table.add_column("Bet", justify="right")
    table.add_column("Best", justify="right", style="bold")

    for i, r in enumerate(sorted_results, 1):
        status = "[green]✓ UP[/]" if r.is_up else "[red]✗ DOWN[/]"
        ssl_icon = "🔒" if r.ssl_valid else "⚠️"

        table.add_row(
            str(i),
            f"{r.mirror.domain} {ssl_icon}",
            status,
            r.ip_address or "—",
            r.server_location or "—",
            f"[{latency_color(r.dns_resolve_ms)}]{fmt_ms(r.dns_resolve_ms)}[/]",
            f"[{latency_color(r.tcp_latency_ms)}]{fmt_ms(r.tcp_latency_ms)}[/]",
            f"[{latency_color(r.https_latency_ms)}]{fmt_ms(r.https_latency_ms)}[/]",
            f"[{latency_color(r.api_latency_ms)}]{fmt_ms(r.api_latency_ms)}[/]",
            f"[{latency_color(r.bet_latency_ms)}]{fmt_ms(r.bet_latency_ms)}[/]",
            f"[{latency_color(r.best_latency_ms)}]{fmt_ms(r.best_latency_ms)}[/]",
        )

    console.print()
    console.print(table)
    console.print()

    # Winner announcement
    if sorted_results and sorted_results[0].is_up:
        winner = sorted_results[0]
        console.print(Panel(
            f"[bold green]🏆 FASTEST MIRROR: {winner.mirror.domain}[/]\n"
            f"   Best latency: {fmt_ms(winner.best_latency_ms)}\n"
            f"   Location: {winner.server_location or 'Unknown'}\n"
            f"   URL: {winner.mirror.url}",
            title="Winner",
            border_style="green",
        ))


def print_vpn_recommendations(
    recommendations: dict[str, list[VPNRecommendation]],
) -> None:
    """Print NordVPN recommendations table."""
    if not recommendations:
        console.print("[yellow]No VPN recommendations available (GeoIP data missing)[/]")
        return

    table = Table(
        title="🌍 NordVPN Region Recommendations (Europe)",
        show_lines=True,
        title_style="bold magenta",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Mirror", style="bold")
    table.add_column("VPN Server", style="cyan")
    table.add_column("VPN City", style="green")
    table.add_column("VPN Country")
    table.add_column("Distance", justify="right")
    table.add_column("Mirror Ping", justify="right")
    table.add_column("Est. Total", justify="right", style="bold")

    # Flatten and sort by estimated total latency
    all_recs = []
    for domain, recs in recommendations.items():
        if recs:
            all_recs.append(recs[0])  # Best VPN per mirror

    all_recs.sort(key=lambda r: r.estimated_latency_ms)

    for i, rec in enumerate(all_recs, 1):
        table.add_row(
            str(i),
            rec.mirror.domain,
            rec.vpn_server.hostname,
            rec.vpn_server.city,
            rec.vpn_server.country,
            f"{rec.distance_km:.0f} km",
            f"[{latency_color(rec.mirror_latency_ms)}]{fmt_ms(rec.mirror_latency_ms)}[/]",
            f"[{latency_color(rec.estimated_latency_ms)}]{fmt_ms(rec.estimated_latency_ms)}[/]",
        )

    console.print()
    console.print(table)
    console.print()

    if all_recs:
        best = all_recs[0]
        console.print(Panel(
            f"[bold magenta]🎯 RECOMMENDED SETUP:[/]\n"
            f"   NordVPN → [bold]{best.vpn_server.city}, {best.vpn_server.country}[/]\n"
            f"   Mirror  → [bold]{best.mirror.domain}[/]\n"
            f"   Est. latency: {fmt_ms(best.estimated_latency_ms)}",
            title="Best VPN + Mirror Combo",
            border_style="magenta",
        ))


def export_results(
    results: list[PingResult],
    recommendations: dict[str, list[VPNRecommendation]],
    fmt: str = "json",
    output_dir: str = "results",
) -> str:
    """Export results to JSON or CSV."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if fmt == "json":
        filepath = os.path.join(output_dir, f"results_{timestamp}.json")
        data = {
            "timestamp": datetime.now().isoformat(),
            "mirrors": [],
            "vpn_recommendations": [],
        }
        for r in sorted(results, key=lambda x: x.best_latency_ms or 99999):
            data["mirrors"].append({
                "domain": r.mirror.domain,
                "url": r.mirror.url,
                "is_up": r.is_up,
                "ip": r.ip_address,
                "location": r.server_location,
                "dns_ms": r.dns_resolve_ms,
                "tcp_ms": r.tcp_latency_ms,
                "https_ms": r.https_latency_ms,
                "api_ms": r.api_latency_ms,
                "bet_ms": r.bet_latency_ms,
                "best_ms": r.best_latency_ms,
                "ssl_valid": r.ssl_valid,
                "error": r.error,
            })
        for domain, recs in recommendations.items():
            for rec in recs:
                data["vpn_recommendations"].append({
                    "mirror": rec.mirror.domain,
                    "vpn_server": rec.vpn_server.hostname,
                    "vpn_city": rec.vpn_server.city,
                    "vpn_country": rec.vpn_server.country,
                    "distance_km": rec.distance_km,
                    "mirror_latency_ms": rec.mirror_latency_ms,
                    "estimated_total_ms": rec.estimated_latency_ms,
                })
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    elif fmt == "csv":
        filepath = os.path.join(output_dir, f"results_{timestamp}.csv")
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Rank", "Domain", "URL", "Status", "IP", "Location",
                "DNS_ms", "TCP_ms", "HTTPS_ms", "API_ms", "Bet_ms",
                "Best_ms", "SSL", "Error",
            ])
            for i, r in enumerate(
                sorted(results, key=lambda x: x.best_latency_ms or 99999), 1
            ):
                writer.writerow([
                    i, r.mirror.domain, r.mirror.url,
                    "UP" if r.is_up else "DOWN",
                    r.ip_address, r.server_location,
                    r.dns_resolve_ms, r.tcp_latency_ms, r.https_latency_ms,
                    r.api_latency_ms, r.bet_latency_ms,
                    r.best_latency_ms, r.ssl_valid, r.error,
                ])
    else:
        raise ValueError(f"Unknown format: {fmt}")

    console.print(f"[dim]Results exported to {filepath}[/]")
    return filepath
