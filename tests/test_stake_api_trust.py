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


def test_trusted_label_with_mismatched_url_never_posts():
    mirror = MirrorConfig("trusted.example", "https://evil.example", trusted=True)
    with patch("src.stake_api._cffi_post") as post:
        assert (
            asyncio.run(api_latency_test(mirror, "FAKE-TEST-TOKEN", rounds=1)) is None
        )
    post.assert_not_called()


def test_authenticated_sink_pins_public_dns_and_disables_redirects():
    from unittest.mock import AsyncMock, MagicMock

    from curl_cffi import CurlOpt

    from src.stake_api import _cffi_post

    response = MagicMock(status_code=302)
    with (
        patch(
            "src.stake_api.PublicResolver.resolve",
            AsyncMock(return_value=[{"host": "1.1.1.1"}]),
        ),
        patch("src.stake_api.cffi_requests.post", return_value=response) as post,
    ):
        assert _cffi_post("https://example.com/_api/graphql", "{}", {}, {}) == (
            302,
            None,
        )
    options = post.call_args.kwargs
    assert options["allow_redirects"] is False and options["verify"] is True
    assert options["curl_options"][CurlOpt.PROXY] == ""
    assert options["curl_options"][CurlOpt.RESOLVE] == ["example.com:443:1.1.1.1"]


def test_authenticated_sink_rejects_private_dns():
    from unittest.mock import AsyncMock

    from src.stake_api import _cffi_post

    with (
        patch(
            "src.stake_api.PublicResolver.resolve",
            AsyncMock(side_effect=ValueError("private")),
        ),
        patch("src.stake_api.cffi_requests.post") as post,
    ):
        assert _cffi_post("https://example.com/_api/graphql", "{}", {}, {}) == (0, None)
    post.assert_not_called()
