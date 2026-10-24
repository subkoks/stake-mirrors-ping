"""Deterministic discovery, destination and scan-input regression coverage."""

import asyncio
import socket
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from src.core.orchestrator import (
    OrchestratorConfig,
    load_config,
    parse_mirrors,
    run_scan,
)
from src.mirror_update import atomic_write, build_refresh, parse_source
from src.mirror_validation import (
    PublicResolver,
    normalize_destination,
    public_ip,
    validate_settings,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com/path",
        "https://127.0.0.1",
        "https://example.com:123",
        "file:///etc/passwd",
        "https://example.com?q=x",
        "https://example.com#x",
        "https://example.com\\@other.com",
    ],
)
def test_discovery_rejects_malformed_or_nonstandard_origins(url):
    with pytest.raises(ValueError):
        parse_source([url])


def test_discovery_normalizes_and_deduplicates():
    assert parse_source(["https://EXAMPLE.com/", "https://example.com"]) == [
        {"domain": "example.com", "url": "https://example.com"}
    ]
    assert (
        normalize_destination("bücher.de", "https://bücher.de")[0] == "xn--bcher-kva.de"
    )


@pytest.mark.parametrize("data", [[], {}, None, ["https://example.com", None]])
def test_bad_source_is_rejected(data):
    with pytest.raises(ValueError):
        parse_source(data)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "::1",
        "fc00::1",
        "fe80::1",
        "::ffff:127.0.0.1",
        "224.0.0.1",
    ],
)
def test_nonpublic_addresses(address):
    with pytest.raises(ValueError):
        public_ip(address)


def test_mixed_dns_answers_fail_closed():
    async def check():
        records = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]
        with patch.object(
            asyncio.get_running_loop(), "getaddrinfo", AsyncMock(return_value=records)
        ):
            with pytest.raises(ValueError):
                await PublicResolver().resolve("example.com", 443)

    asyncio.run(check())


def test_dns_timeout_is_bounded():
    async def check():
        async def slow(*args, **kwargs):
            await asyncio.sleep(10)

        with patch.object(asyncio.get_running_loop(), "getaddrinfo", slow):
            with pytest.raises(TimeoutError):
                await PublicResolver(0.001).resolve("example.com", 443)

    asyncio.run(check())


def test_custom_entries_comments_and_settings_are_preserved():
    original = "# config\nmirrors:\n  - domain: example.com\n    url: https://example.com\n    custom: keep\n\nsettings:\n  ping_rounds: 2 # comment\n"
    entries = parse_source(["https://another.com"])
    text, report = build_refresh(original, entries, {"listed_domains": ["example.com"]})
    assert "custom: keep" in text and "ping_rounds: 2 # comment" in text
    assert report["retained_not_listed"] == ["example.com"]
    assert report["removed"] == [] and report["requires_review"]
    assert len(parse_mirrors(yaml.safe_load(text))) == 2


def test_atomic_replace_failure_preserves_last_known_good(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("original")
    with patch("src.mirror_update.os.replace", side_effect=OSError("disk error")):
        with pytest.raises(OSError):
            atomic_write(path, "replacement")
    assert path.read_text() == "original"
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize(
    "values", [(0, 1, 1), (1, float("nan"), 1), (1, 1, 0), (True, 1, 1), (1, 1, 1000)]
)
def test_settings_bounds(values):
    with pytest.raises(ValueError):
        validate_settings(*values)


def test_mismatch_and_duplicate_rejected():
    with pytest.raises(ValueError):
        parse_mirrors(
            {"mirrors": [{"domain": "example.com", "url": "https://another.com"}]}
        )
    with pytest.raises(ValueError):
        parse_mirrors(
            {"mirrors": [{"domain": "example.com", "url": "https://example.com"}] * 2}
        )


def test_all_source_and_retained_entries_reach_scan_input(monkeypatch):
    config = load_config()
    from pathlib import Path

    snapshot = yaml.safe_load(Path("docs/mirrors/source-snapshot.yaml").read_text())
    expected = {m.domain for m in parse_mirrors(config)}
    assert set(snapshot["listed_domains"]) <= expected
    captured = []

    async def fake_ping(mirrors, **kwargs):
        captured.extend(m.domain for m in mirrors)
        assert kwargs["concurrency"] == config["settings"]["concurrent_limit"]
        return []

    monkeypatch.setattr("src.core.orchestrator.ping_all_mirrors", fake_ping)
    asyncio.run(
        run_scan(OrchestratorConfig(skip_geoip=True, skip_vpn=True, save_history=False))
    )
    assert set(captured) == expected


def test_apply_refuses_partial_source_without_writes(tmp_path, monkeypatch):
    from src.mirror_update import main

    config = tmp_path / "config.yaml"
    config.write_text(
        "mirrors:\n  - domain: example.com\n    url: https://example.com\n"
    )
    snapshot = tmp_path / "snapshot.yaml"
    snapshot.write_text("listed_domains: [example.com, another.com]\n")
    original = config.read_bytes(), snapshot.read_bytes()
    monkeypatch.setattr(
        "src.mirror_update.fetch_source",
        AsyncMock(return_value=(parse_source(["https://example.com"]), "fixture-time")),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["refresh", "--apply", "--config", str(config), "--snapshot", str(snapshot)],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert (config.read_bytes(), snapshot.read_bytes()) == original


def test_source_failure_preserves_files(tmp_path, monkeypatch):
    from src.mirror_update import main

    config = tmp_path / "config.yaml"
    config.write_text(
        "mirrors:\n  - domain: example.com\n    url: https://example.com\n"
    )
    snapshot = tmp_path / "snapshot.yaml"
    monkeypatch.setattr(
        "src.mirror_update.fetch_source", AsyncMock(side_effect=TimeoutError())
    )
    monkeypatch.setattr(
        "sys.argv",
        ["refresh", "--apply", "--config", str(config), "--snapshot", str(snapshot)],
    )
    original = config.read_bytes()
    with pytest.raises(SystemExit):
        main()
    assert config.read_bytes() == original and not snapshot.exists()


def test_invalid_gui_settings_cannot_inject_or_corrupt_yaml(tmp_path):
    from src.core.api import _patch_settings_block

    config = tmp_path / "config.yaml"
    config.write_text("settings:\n  ping_rounds: 3\n")
    original = config.read_bytes()
    with pytest.raises(ValueError):
        _patch_settings_block(config, {"ping_rounds": "3\nmirrors: []"})
    assert config.read_bytes() == original


def test_chunked_source_is_read_to_eof(monkeypatch):
    import json

    from src.mirror_update import fetch_source

    class Content:
        async def iter_chunked(self, size):
            for chunk in [b'["https://', b"example.com", b'"]']:
                yield chunk

    response = AsyncMock(status=200)
    response.content = Content()
    response.__aenter__.return_value = response
    session = AsyncMock()
    session.get = lambda *args, **kwargs: response
    session.__aenter__.return_value = session
    with patch("src.mirror_update.aiohttp.ClientSession", return_value=session):
        entries, timestamp = asyncio.run(fetch_source())
    assert entries == parse_source(json.loads('["https://example.com"]'))
    assert timestamp
