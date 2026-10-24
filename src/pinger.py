import asyncio
import socket
import ssl
import time
from collections.abc import Callable
from urllib.parse import urlsplit

import aiohttp
import certifi

from .log import logger
from .mirror_validation import (
    PublicResolver,
    normalize_destination,
    public_ip,
    validate_settings,
)
from .models import MirrorConfig, PingResult


async def tcp_ping(host: str, port: int = 443, timeout: float = 10.0) -> float | None:
    """Connect only to an already validated public numeric address."""
    writer = None
    try:
        public_ip(host)
        start = time.perf_counter()
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
        return round((time.perf_counter() - start) * 1000, 2)
    except (OSError, TimeoutError, ValueError) as exc:
        logger.debug("TCP probe failed: %s", type(exc).__name__)
        return None
    finally:
        if writer is not None:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout)
            except (OSError, TimeoutError):
                pass


async def https_ping(
    url: str,
    timeout: float = 10.0,
    session: aiohttp.ClientSession | None = None,
    errors: list[str] | None = None,
) -> tuple[float | None, int | None, bool]:
    """Measure one origin HEAD, without following untrusted redirects."""
    own_session = session is None
    parsed = urlsplit(url)
    normalize_destination(parsed.hostname or "", url)
    if own_session:
        session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                resolver=PublicResolver(timeout), family=socket.AF_UNSPEC
            )
        )
    try:
        start = time.perf_counter()
        async with session.head(  # type: ignore[union-attr]
            url,
            timeout=aiohttp.ClientTimeout(total=timeout),
            ssl=ssl.create_default_context(cafile=certifi.where()),
            allow_redirects=False,
        ) as resp:
            return (
                round((time.perf_counter() - start) * 1000, 2),
                resp.status,
                parsed.scheme == "https",
            )
    except (ssl.SSLError, aiohttp.ClientSSLError):
        if errors is not None:
            errors.append("tls_error")
        return None, None, False
    except TimeoutError:
        if errors is not None:
            errors.append("http_timeout")
        return None, None, False
    except ValueError:
        if errors is not None:
            errors.append("destination_rejected")
        return None, None, False
    except (aiohttp.ClientError, OSError):
        if errors is not None:
            errors.append("http_connection_error")
        return None, None, False
    finally:
        if own_session:
            await session.close()  # type: ignore[union-attr]


async def dns_resolve(
    domain: str, timeout: float = 10.0, port: int = 443
) -> tuple[str | None, float | None]:
    """Bound DNS time and reject the entire answer if any address is non-public."""
    start = time.perf_counter()
    answers = await PublicResolver(timeout).resolve(domain, port, socket.AF_UNSPEC)
    return answers[0]["host"], round((time.perf_counter() - start) * 1000, 2)


def classify_http(status: int | None) -> str:
    if status is None:
        return "http_unavailable"
    if status in (401, 403):
        return "blocked_or_challenged"
    if status == 429:
        return "rate_limited"
    if 300 <= status < 400:
        return "redirect_unverified"
    if 200 <= status < 300:
        return "http_responding"
    return "http_error"


async def ping_mirror(
    mirror: MirrorConfig, rounds: int = 3, timeout: float = 10.0
) -> PingResult:
    result = PingResult(mirror=mirror)
    domain, url = normalize_destination(mirror.domain, mirror.url)
    parsed = urlsplit(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        result.ip_address, result.dns_resolve_ms = await dns_resolve(
            domain, timeout, port
        )
    except TimeoutError:
        result.reachability = "dns_timeout"
        result.error = "Local DNS lookup timed out; remote status unknown"
        return result
    except ValueError:
        result.reachability = "destination_rejected"
        result.error = "Destination resolved to a non-public address"
        return result
    except OSError:
        result.reachability = "dns_error"
        result.error = "Local DNS lookup failed; remote status unknown"
        return result

    tcp_times = []
    for _ in range(rounds):
        value = await tcp_ping(result.ip_address, port, timeout)  # type: ignore[arg-type]
        if value is not None:
            tcp_times.append(value)
    result.tcp_latency_ms = (
        round(sum(tcp_times) / len(tcp_times), 2) if tcp_times else None
    )

    times, statuses, valid = [], [], []
    errors: list[str] = []
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(
            resolver=PublicResolver(timeout), family=socket.AF_UNSPEC
        )
    ) as session:
        for _ in range(rounds):
            latency, status, ssl_ok = await https_ping(
                url, timeout, session, errors=errors
            )
            valid.append(ssl_ok)
            if latency is not None:
                times.append(latency)
            statuses.append(status)
    result.https_latency_ms = round(sum(times) / len(times), 2) if times else None
    result.ssl_valid = all(valid)
    # A failed/blocked round must not be hidden behind a successful first round.
    result.http_status = next(
        (s for s in statuses if s is None or not 200 <= s < 300), statuses[0]
    )
    result.reachability = (
        errors[0]
        if result.http_status is None and errors
        else classify_http(result.http_status)
    )
    if result.http_status is None:
        result.error = (
            "Local HTTP/TLS request failed or timed out; remote status unknown"
        )
    result.is_up = all(s is not None and 200 <= s < 300 for s in statuses) and bool(
        times
    )
    return result


async def ping_all_mirrors(
    mirrors: list[MirrorConfig],
    rounds: int = 3,
    timeout: float = 10.0,
    concurrency: int = 16,
    progress: Callable[[int, int], None] | None = None,
) -> list[PingResult]:
    rounds, timeout, concurrency = validate_settings(rounds, timeout, concurrency)
    sem = asyncio.Semaphore(concurrency)

    completed = 0

    async def limited(mirror: MirrorConfig) -> PingResult:
        nonlocal completed
        async with sem:
            result = await ping_mirror(mirror, rounds, timeout)
            completed += 1
            if progress is not None:
                progress(completed, len(mirrors))
            return result

    tasks = [asyncio.create_task(limited(m)) for m in mirrors]
    try:
        return await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
