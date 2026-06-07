import asyncio
import ipaddress
from typing import Optional

import aiohttp

from .models import PingResult


GEOIP_API = "https://api.ipquery.io/"


async def geoip_lookup(
    ip: str, session: Optional[aiohttp.ClientSession] = None
) -> dict:
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
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status == 200:
                return await resp.json()
            return {}
    except Exception:
        return {}
    finally:
        if own_session:
            await session.close()


async def enrich_with_geoip(results: list[PingResult]) -> list[PingResult]:
    """Add GeoIP data to all ping results."""
    async with aiohttp.ClientSession() as session:
        for result in results:
            if result.ip_address:
                geo = await geoip_lookup(result.ip_address, session)
                location = geo.get("location", {})
                if location:
                    result.server_country = location.get("country", "Unknown")
                    result.server_city = location.get("city", "Unknown")
                    result.server_location = (
                        f"{location.get('city', '?')}, {location.get('country', '?')}"
                    )
                    result.server_lat = location.get("latitude")
                    result.server_lon = location.get("longitude")
    return results
