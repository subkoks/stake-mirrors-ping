"""Security regression tests: the session token must never reach untrusted mirrors."""

import asyncio
from unittest.mock import patch

from src.models import MirrorConfig, PingResult
from src.stake_api import api_latency_test, bet_latency_test, enrich_with_api_tests


def _result(domain: str, *, trusted: bool, is_up: bool = True) -> PingResult:
    return PingResult(
        mirror=MirrorConfig(domain=domain, url=f"https://{domain}", trusted=trusted),
        is_up=is_up,
    )


def test_api_latency_test_skips_untrusted_without_posting():
    mirror = MirrorConfig(
        domain="evil.example", url="https://evil.example", trusted=False
    )
    with patch("src.stake_api._cffi_post") as post:
        out = asyncio.run(api_latency_test(mirror, "SECRET", rounds=1))
    assert out is None
    post.assert_not_called()  # token never sent


def test_bet_latency_test_skips_untrusted_without_posting():
    mirror = MirrorConfig(
        domain="evil.example", url="https://evil.example", trusted=False
    )
    with patch("src.stake_api._cffi_post") as post:
        out = asyncio.run(bet_latency_test(mirror, "SECRET"))
    assert out is None
    post.assert_not_called()


def test_enrich_only_posts_to_trusted_mirrors():
    results = [
        _result("trusted.example", trusted=True),
        _result("evil.example", trusted=False),
    ]
    posted_urls: list[str] = []

    def fake_post(url, payload, headers, cookies, timeout=10.0):
        posted_urls.append(url)
        return 200, {"data": {}}

    with patch("src.stake_api._cffi_post", side_effect=fake_post):
        asyncio.run(enrich_with_api_tests(results, "SECRET", rounds=1))

    assert all("trusted.example" in u for u in posted_urls)
    assert not any("evil.example" in u for u in posted_urls)
