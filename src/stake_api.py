import asyncio
import json
import time
from typing import Optional

import aiohttp
import websockets

from rich.console import Console

from .models import MirrorConfig, PingResult

console = Console()


GRAPHQL_PATH = "/_api/graphql"
WS_PATH = "/_api/graphql"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

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


async def api_latency_test(
    mirror: MirrorConfig,
    session_token: str,
    rounds: int = 3,
    timeout: float = 10.0,
) -> Optional[float]:
    """Test API latency by making authenticated GraphQL requests."""
    url = f"{mirror.url}{GRAPHQL_PATH}"
    headers = {
        **BROWSER_HEADERS,
        "x-access-token": session_token,
        "Content-Type": "application/json",
        "Origin": mirror.url,
        "Referer": f"{mirror.url}/",
    }
    cookies = {"session": session_token}
    payload = json.dumps({"query": BALANCE_QUERY})

    times = []
    async with aiohttp.ClientSession(cookies=cookies) as session:
        for _ in range(rounds):
            try:
                start = time.perf_counter()
                async with session.post(
                    url,
                    data=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    ssl=True,
                ) as resp:
                    elapsed = (time.perf_counter() - start) * 1000
                    if resp.status == 200:
                        data = await resp.json()
                        if "errors" not in data:
                            times.append(round(elapsed, 2))
            except Exception:
                pass
            await asyncio.sleep(0.2)

    return round(sum(times) / len(times), 2) if times else None


async def ws_latency_test(
    mirror: MirrorConfig,
    session_token: str,
    timeout: float = 10.0,
) -> Optional[float]:
    """Test WebSocket connection + message latency.

    Note: May fail due to Cloudflare blocking raw WebSocket upgrades.
    """
    ws_url = f"wss://{mirror.domain}{WS_PATH}"
    headers = {
        **BROWSER_HEADERS,
        "x-access-token": session_token,
        "Cookie": f"session={session_token}",
    }

    try:
        start = time.perf_counter()
        async with websockets.connect(
            ws_url,
            additional_headers=headers,
            open_timeout=timeout,
        ) as ws:
            connect_time = (time.perf_counter() - start) * 1000

            # Send connection_init for GraphQL WS protocol
            init_msg = json.dumps({"type": "connection_init", "payload": {}})
            start = time.perf_counter()
            await ws.send(init_msg)
            response = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msg_time = (time.perf_counter() - start) * 1000

            return round((connect_time + msg_time) / 2, 2)
    except Exception:
        return None


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
        **BROWSER_HEADERS,
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

    try:
        async with aiohttp.ClientSession(cookies=cookies) as session:
            start = time.perf_counter()
            async with session.post(
                url,
                data=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
                ssl=True,
            ) as resp:
                elapsed = (time.perf_counter() - start) * 1000
                if resp.status == 200:
                    data = await resp.json()
                    if "errors" not in data:
                        return round(elapsed, 2)
    except Exception:
        pass
    return None


async def enrich_with_api_tests(
    results: list[PingResult],
    session_token: str,
    rounds: int = 3,
    run_bets: bool = False,
) -> list[PingResult]:
    """Add API/WS/bet latency data to ping results."""
    ws_warned = False
    bet_warned = False

    for result in results:
        if not result.is_up:
            continue

        # API latency
        result.api_latency_ms = await api_latency_test(
            result.mirror, session_token, rounds=rounds
        )

        # WebSocket latency (skip all if first mirror fails — Cloudflare blocks raw WS)
        if not ws_warned:
            result.ws_latency_ms = await ws_latency_test(
                result.mirror, session_token
            )
            if result.ws_latency_ms is None:
                console.print("[yellow]⚠ WebSocket test failed (Cloudflare blocks raw WS connections) — skipping WS for remaining mirrors[/]")
                ws_warned = True

        # Bet latency (only if explicitly enabled)
        if run_bets and not bet_warned:
            result.bet_latency_ms = await bet_latency_test(
                result.mirror, session_token
            )
            if result.bet_latency_ms is None:
                console.print("[yellow]⚠ Bet test failed (geo-blocked or mutation changed) — skipping bets for remaining mirrors[/]")
                bet_warned = True
        elif run_bets and bet_warned:
            pass  # skip — already warned

        await asyncio.sleep(0.3)

    return results
