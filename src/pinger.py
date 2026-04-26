import asyncio
import socket
import ssl
import time
from typing import Optional

import aiohttp
import certifi

from .models import MirrorConfig, PingResult
from .log import logger


async def tcp_ping(host: str, port: int = 443, timeout: float = 10.0) -> Optional[float]:
    """Measure TCP connect latency in ms."""
    try:
        start = time.perf_counter()
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        elapsed = (time.perf_counter() - start) * 1000
        writer.close()
        await writer.wait_closed()
        return round(elapsed, 2)
    except Exception as e:
        logger.debug("tcp_ping failed for %s: %s", host, e)
        return None


async def https_ping(
    url: str, timeout: float = 10.0, session: Optional[aiohttp.ClientSession] = None
) -> tuple[Optional[float], Optional[int], bool]:
    """Measure HTTPS HEAD request latency. Returns (latency_ms, status_code, ssl_valid)."""
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()
    try:
        start = time.perf_counter()
        async with session.head(
            url,
            timeout=aiohttp.ClientTimeout(total=timeout),
            ssl=ssl_ctx,
            allow_redirects=True,
        ) as resp:
            elapsed = (time.perf_counter() - start) * 1000
            return round(elapsed, 2), resp.status, True
    except ssl.SSLError:
        return None, None, False
    except Exception as e:
        logger.debug("https_ping failed for %s: %s", url, e)
        return None, None, True
    finally:
        if own_session:
            await session.close()


async def dns_resolve(domain: str) -> tuple[Optional[str], Optional[float]]:
    """Resolve domain to IP and measure DNS lookup time."""
    try:
        start = time.perf_counter()
        loop = asyncio.get_running_loop()
        result = await loop.getaddrinfo(domain, 443, family=socket.AF_INET)
        elapsed = (time.perf_counter() - start) * 1000
        ip = result[0][4][0] if result else None
        return ip, round(elapsed, 2)
    except Exception as e:
        logger.debug("dns_resolve failed for %s: %s", domain, e)
        return None, None


async def ping_mirror(
    mirror: MirrorConfig,
    rounds: int = 3,
    timeout: float = 10.0,
) -> PingResult:
    """Run full ping suite on a single mirror."""
    result = PingResult(mirror=mirror)

    # DNS resolve
    ip, dns_ms = await dns_resolve(mirror.domain)
    result.ip_address = ip
    result.dns_resolve_ms = dns_ms

    if not ip:
        result.error = "DNS resolution failed"
        return result

    # TCP ping (average over rounds)
    tcp_times = []
    for _ in range(rounds):
        t = await tcp_ping(ip, timeout=timeout)
        if t is not None:
            tcp_times.append(t)
        await asyncio.sleep(0.1)
    result.tcp_latency_ms = round(sum(tcp_times) / len(tcp_times), 2) if tcp_times else None

    # HTTPS ping (average over rounds)
    https_times = []
    statuses = []
    ssl_valid = True
    async with aiohttp.ClientSession() as session:
        for _ in range(rounds):
            latency, status, ssl_ok = await https_ping(mirror.url, timeout=timeout, session=session)
            if latency is not None:
                https_times.append(latency)
            if status is not None:
                statuses.append(status)
            if not ssl_ok:
                ssl_valid = False
            await asyncio.sleep(0.1)

    result.https_latency_ms = round(sum(https_times) / len(https_times), 2) if https_times else None
    result.ssl_valid = ssl_valid
    result.http_status = statuses[0] if statuses else None
    result.is_up = bool(https_times and statuses and statuses[0] in (200, 301, 302, 403))

    return result


async def ping_all_mirrors(
    mirrors: list[MirrorConfig],
    rounds: int = 3,
    timeout: float = 10.0,
    concurrency: int = 16,
) -> list[PingResult]:
    """Ping all mirrors concurrently."""
    sem = asyncio.Semaphore(concurrency)

    async def _limited(m: MirrorConfig) -> PingResult:
        async with sem:
            return await ping_mirror(m, rounds=rounds, timeout=timeout)

    tasks = [_limited(m) for m in mirrors]
    return await asyncio.gather(*tasks)
