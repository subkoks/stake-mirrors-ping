import asyncio
from typing import Optional

import aiohttp

from .models import PingResult


GEOIP_API = "http://ip-api.com/json/"
GEOIP_FIELDS = "status,country,city,lat,lon,isp,org,query"


async def geoip_lookup(ip: str, session: Optional[aiohttp.ClientSession] = None) -> dict:
    """Lookup GeoIP info for an IP address using ip-api.com (free, no key needed)."""
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()
    try:
        url = f"{GEOIP_API}{ip}?fields={GEOIP_FIELDS}"
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
    # ip-api.com has rate limit of 45 req/min for free tier, batch carefully
    async with aiohttp.ClientSession() as session:
        for result in results:
            if result.ip_address:
                geo = await geoip_lookup(result.ip_address, session)
                if geo.get("status") == "success":
                    result.server_country = geo.get("country", "Unknown")
                    result.server_city = geo.get("city", "Unknown")
                    result.server_location = f"{geo.get('city', '?')}, {geo.get('country', '?')}"
                    result.server_lat = geo.get("lat")
                    result.server_lon = geo.get("lon")
                # Rate limit: 45/min free tier
                await asyncio.sleep(1.5)
    return results
