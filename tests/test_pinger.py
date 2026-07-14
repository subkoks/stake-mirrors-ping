"""Tests for pinger SSL-validity semantics."""

import asyncio
import ssl
from unittest.mock import AsyncMock

from src.pinger import https_ping


def test_ssl_valid_false_on_non_ssl_error() -> None:
    """Any non-SSL failure (timeout, connection error) must NOT imply valid TLS."""
    fake_session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__.side_effect = OSError("connection failed")
    fake_session.head.return_value = ctx

    latency, status, ssl_valid = asyncio.run(
        https_ping("https://example.com", timeout=1, session=fake_session)
    )
    assert latency is None
    assert status is None
    assert ssl_valid is False


def test_ssl_valid_false_on_ssleror() -> None:
    fake_session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__.side_effect = ssl.SSLError("cert verify failed")
    fake_session.head.return_value = ctx

    _latency, _status, ssl_valid = asyncio.run(
        https_ping("https://example.com", timeout=1, session=fake_session)
    )
    assert ssl_valid is False
