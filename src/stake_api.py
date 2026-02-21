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
            url, data=payload, headers=headers, cookies=cookies,
            impersonate="chrome", timeout=timeout,
        )
        return r.status_code, r.json() if r.status_code == 200 else None
    except Exception:
        return 0, None


async def api_latency_test(
    mirror: MirrorConfig,
    session_token: str,
    rounds: int = 3,
    timeout: float = 10.0,
) -> Optional[float]:
    """Test API latency via curl_cffi (Chrome TLS fingerprint bypasses Cloudflare)."""
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
    url = f"{mirror.url}{GRAPHQL_PATH}"
    headers = {
        "x-access-token": session_token,
        "Content-Type": "application/json",
        "Origin": mirror.url,
        "Referer": f"{mirror.url}/",
    }
    cookies = {"session": session_token}
    payload = json.dumps({
        "query": MINES_BET_MUTATION,
        "variables": {
            "amount": 0,
            "currency": "btc",
        },
    })

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
    """Add API/bet latency data to ping results (concurrent)."""
    sem = asyncio.Semaphore(concurrency)
    up_results = [r for r in results if r.is_up]

    if not up_results:
        return results

    # Probe first mirror to detect bet failures before mass-testing
    probe = up_results[0]
    probe.api_latency_ms = await api_latency_test(
        probe.mirror, session_token, rounds=rounds
    )

    bet_works = False
    if run_bets:
        probe.bet_latency_ms = await bet_latency_test(probe.mirror, session_token)
        bet_works = probe.bet_latency_ms is not None
        if not bet_works:
            console.print("[yellow]⚠ Bet test failed (geo-blocked or mutation changed) — skipping bets[/]")

    # Run remaining mirrors concurrently
    remaining = up_results[1:]
    if remaining:
        tasks = [
            _test_single_mirror(
                r, session_token, rounds,
                run_bets=run_bets and bet_works,
                sem=sem,
            )
            for r in remaining
        ]
        await asyncio.gather(*tasks)

    return results
