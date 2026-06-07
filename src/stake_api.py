import asyncio
import json
import time
from typing import Optional

from curl_cffi import requests as cffi_requests

from rich.console import Console

from .models import MirrorConfig, PingResult

console = Console()


GRAPHQL_PATH = "/_api/graphql"

# GraphQL query to check balance (lightweight, good for latency test)
BALANCE_QUERY = """
query UserBalances {
    user {
        balances {
            available {
                amount
                currency
            }
        }
    }
}
"""

# Mines bet mutation ($0 bet — used as latency proxy since casinoBet was removed)
MINES_BET_MUTATION = """
mutation MinesBet($amount: Float!, $currency: CurrencyEnum!) {
    minesBet(amount: $amount, currency: $currency, minesCount: 1) {
        id
        payoutMultiplier
    }
}
"""


def _cffi_post(
    url: str,
    payload: str,
    headers: dict,
    cookies: dict,
    timeout: float = 10.0,
) -> tuple[int, Optional[dict]]:
    """Synchronous curl_cffi POST with Chrome TLS fingerprint."""
    try:
        r = cffi_requests.post(
            url,
            data=payload,
            headers=headers,
            cookies=cookies,
            impersonate="chrome",
            timeout=timeout,
            verify=True,  # never disable cert verification when sending the token
        )
        return r.status_code, r.json() if r.status_code == 200 else None
    except Exception:
        return 0, None


def _require_trusted(mirror: MirrorConfig) -> bool:
    """Guard the token sink: refuse to send credentials to untrusted mirrors.

    The Stake session token grants real-money account access. Sending it to an
    unverified mirror (a lapsed/squatted/phishing domain) is account takeover.
    Only mirrors explicitly marked ``trusted`` in config / STAKE_TRUSTED_DOMAINS
    receive it; everything else is ranked by unauthenticated TCP/HTTPS latency.
    """
    if not mirror.trusted:
        console.print(
            f"[yellow]⚠ Skipping authenticated API test for untrusted mirror "
            f"{mirror.domain} — token withheld. Add it to "
            f"settings.trusted_api_domains (or STAKE_TRUSTED_DOMAINS) only if you "
            f"have verified it is genuinely yours.[/]"
        )
        return False
    return True


async def api_latency_test(
    mirror: MirrorConfig,
    session_token: str,
    rounds: int = 3,
    timeout: float = 10.0,
) -> Optional[float]:
    """Test API latency via curl_cffi (Chrome TLS fingerprint bypasses Cloudflare)."""
    if not _require_trusted(mirror):
        return None
    url = f"{mirror.url}{GRAPHQL_PATH}"
    headers = {
        "x-access-token": session_token,
        "Content-Type": "application/json",
        "Origin": mirror.url,
        "Referer": f"{mirror.url}/",
    }
    cookies = {"session": session_token}
    payload = json.dumps({"query": BALANCE_QUERY})

    times = []
    for _ in range(rounds):
        start = time.perf_counter()
        status, data = await asyncio.to_thread(
            _cffi_post, url, payload, headers, cookies, timeout
        )
        elapsed = (time.perf_counter() - start) * 1000
        if status == 200 and data and "errors" not in data:
            times.append(round(elapsed, 2))
        await asyncio.sleep(0.1)

    return round(sum(times) / len(times), 2) if times else None


async def bet_latency_test(
    mirror: MirrorConfig,
    session_token: str,
    timeout: float = 10.0,
) -> Optional[float]:
    """Test bet placement latency with $0 Dice bet.

    Note: casinoBet mutation was removed from Stake's GraphQL schema.
    This currently tests a minesBet mutation as a latency proxy.
    """
    if not _require_trusted(mirror):
        return None
    url = f"{mirror.url}{GRAPHQL_PATH}"
    headers = {
        "x-access-token": session_token,
        "Content-Type": "application/json",
        "Origin": mirror.url,
        "Referer": f"{mirror.url}/",
    }
    cookies = {"session": session_token}
    payload = json.dumps(
        {
            "query": MINES_BET_MUTATION,
            "variables": {
                "amount": 0,
                "currency": "btc",
            },
        }
    )

    start = time.perf_counter()
    status, data = await asyncio.to_thread(
        _cffi_post, url, payload, headers, cookies, timeout
    )
    elapsed = (time.perf_counter() - start) * 1000
    if status == 200 and data and "errors" not in data:
        return round(elapsed, 2)
    return None


async def _test_single_mirror(
    result: PingResult,
    session_token: str,
    rounds: int,
    run_bets: bool,
    sem: asyncio.Semaphore,
) -> PingResult:
    """Run API + bet tests for a single mirror behind a semaphore."""
    async with sem:
        result.api_latency_ms = await api_latency_test(
            result.mirror, session_token, rounds=rounds
        )
        if run_bets:
            result.bet_latency_ms = await bet_latency_test(result.mirror, session_token)
        return result


async def enrich_with_api_tests(
    results: list[PingResult],
    session_token: str,
    rounds: int = 3,
    run_bets: bool = False,
    concurrency: int = 4,
) -> list[PingResult]:
    """Add API/bet latency data to ping results (concurrent).

    Authenticated tests only run against mirrors flagged ``trusted`` — the live
    session token is never sent to unverified domains.
    """
    sem = asyncio.Semaphore(concurrency)
    up_results = [r for r in results if r.is_up]
    trusted_results = [r for r in up_results if r.mirror.trusted]
    skipped = len(up_results) - len(trusted_results)
    if skipped:
        console.print(
            f"[yellow]⚠ {skipped} untrusted mirror(s) skipped for authenticated "
            f"API tests — token withheld. Set settings.trusted_api_domains "
            f"(or STAKE_TRUSTED_DOMAINS) for domains you have verified.[/]"
        )

    if not trusted_results:
        if up_results:
            console.print(
                "[yellow]⚠ No trusted mirrors configured — skipping API tests. "
                "Mirrors are still ranked by TCP/HTTPS latency.[/]"
            )
        return results

    # Probe first trusted mirror to detect bet failures before mass-testing
    probe = trusted_results[0]
    probe.api_latency_ms = await api_latency_test(
        probe.mirror, session_token, rounds=rounds
    )

    bet_works = False
    if run_bets:
        probe.bet_latency_ms = await bet_latency_test(probe.mirror, session_token)
        bet_works = probe.bet_latency_ms is not None
        if not bet_works:
            console.print(
                "[yellow]⚠ Bet test failed (geo-blocked or mutation changed) — skipping bets[/]"
            )

    # Run remaining trusted mirrors concurrently
    remaining = trusted_results[1:]
    if remaining:
        tasks = [
            _test_single_mirror(
                r,
                session_token,
                rounds,
                run_bets=run_bets and bet_works,
                sem=sem,
            )
            for r in remaining
        ]
        await asyncio.gather(*tasks)

    return results
