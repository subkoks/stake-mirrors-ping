import math
from typing import Optional

import aiohttp

from .models import NordVPNServer, VPNRecommendation, PingResult


NORDVPN_API = "https://api.nordvpn.com/v1/servers"
NORDVPN_COUNTRIES_API = "https://api.nordvpn.com/v1/servers/countries"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points on Earth in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimate_vpn_latency(distance_km: float, server_load: int) -> float:
    """Rough estimate of VPN overhead in ms based on distance and load.
    
    ~0.01ms per km (fiber speed) + load penalty + base VPN overhead (~15ms).
    """
    base_overhead = 15.0
    distance_latency = distance_km * 0.01
    load_penalty = server_load * 0.1
    return round(base_overhead + distance_latency + load_penalty, 2)


async def fetch_nordvpn_servers(
    target_countries: list[str],
    limit: int = 500,
) -> list[NordVPNServer]:
    """Fetch NordVPN servers for target countries."""
    servers = []
    async with aiohttp.ClientSession() as session:
        # Fetch servers with recommendations (low load, good performance)
        params = {
            "limit": limit,
            "filters[servers_technologies][identifier]": "openvpn_udp",
        }
        try:
            async with session.get(
                NORDVPN_API,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return servers
                data = await resp.json()
        except Exception:
            return servers

    country_set = {c.lower() for c in target_countries}

    for srv in data:
        country_name = srv.get("locations", [{}])[0].get("country", {}).get("name", "")
        city_name = srv.get("locations", [{}])[0].get("country", {}).get("city", {}).get("name", "")
        lat = srv.get("locations", [{}])[0].get("latitude", 0)
        lon = srv.get("locations", [{}])[0].get("longitude", 0)

        if country_name.lower() not in country_set:
            continue

        servers.append(NordVPNServer(
            name=srv.get("name", ""),
            hostname=srv.get("hostname", ""),
            country=country_name,
            city=city_name or country_name,
            lat=float(lat),
            lon=float(lon),
            load=srv.get("load", 0),
        ))

    return servers


def find_best_vpn_for_mirror(
    result: PingResult,
    vpn_servers: list[NordVPNServer],
    top_n: int = 3,
) -> list[VPNRecommendation]:
    """Find the best NordVPN servers for a given mirror based on proximity."""
    if not result.server_lat or not result.server_lon:
        return []

    recommendations = []
    for srv in vpn_servers:
        dist = haversine_km(result.server_lat, result.server_lon, srv.lat, srv.lon)
        vpn_overhead = estimate_vpn_latency(dist, srv.load)
        mirror_latency = result.best_latency_ms or 999
        total = round(mirror_latency + vpn_overhead, 2)

        recommendations.append(VPNRecommendation(
            mirror=result.mirror,
            vpn_server=srv,
            estimated_latency_ms=total,
            distance_km=round(dist, 1),
            mirror_latency_ms=mirror_latency,
        ))

    recommendations.sort(key=lambda r: r.estimated_latency_ms)
    return recommendations[:top_n]


async def get_vpn_recommendations(
    results: list[PingResult],
    target_countries: list[str],
) -> dict[str, list[VPNRecommendation]]:
    """Get VPN recommendations for all mirrors."""
    vpn_servers = await fetch_nordvpn_servers(target_countries)
    if not vpn_servers:
        return {}

    recommendations = {}
    for result in results:
        if result.is_up:
            recs = find_best_vpn_for_mirror(result, vpn_servers)
            if recs:
                recommendations[result.mirror.domain] = recs

    return recommendations
