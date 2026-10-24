import asyncio
import ipaddress

import aiohttp

from .models import PingResult

# Provider is hardcoded here and intentionally HTTPS-only. The legacy
# `geoip:` block in config.yaml was removed because it was never read and
# referenced an insecure http:// endpoint.
GEOIP_API = "https://api.ipquery.io/"


def _apply_geoip(result: PingResult, geo: dict) -> None:
    """Populate GeoIP fields from an ipquery.io response. No-op if absent."""
    location = geo.get("location") or {}
    if not location:
        return
    result.server_country = location.get("country", "Unknown")
    result.server_city = location.get("city", "Unknown")
    result.server_location = (
        f"{location.get('city', '?')}, {location.get('country', '?')}"
    )
    result.server_lat = location.get("latitude")
    result.server_lon = location.get("longitude")


async def geoip_lookup(ip: str, session: aiohttp.ClientSession | None = None) -> dict:
    """Lookup GeoIP info for an IP address over HTTPS."""
    # Validate before interpolating into the URL so a malformed value can't
    # alter the request path/query.
    try:
        ip = str(ipaddress.ip_address(ip))
    except ValueError:
        return {}
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()
    try:
        url = f"{GEOIP_API}{ip}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:  # type: ignore[union-attr]
            if resp.status == 200:
                return await resp.json()  # type: ignore[no-any-return]
            return {}
    except Exception:
        return {}
    finally:
        if own_session:
            await session.close()  # type: ignore[union-attr]


async def enrich_with_geoip(
    results: list[PingResult], concurrency: int = 8
) -> list[PingResult]:
    """Add GeoIP data to all ping results (concurrent, rate-limit bounded)."""
    sem = asyncio.Semaphore(concurrency)

    async def one_ip(ip: str) -> tuple[str, dict]:
        async with sem:
            return ip, await geoip_lookup(ip, session)

    async with aiohttp.ClientSession() as session:
        lookups = await asyncio.gather(
            *(one_ip(ip) for ip in {r.ip_address for r in results if r.ip_address})
        )
    cache = dict(lookups)
    for result in results:
        if result.ip_address:
            _apply_geoip(result, cache.get(result.ip_address, {}))
    return results
