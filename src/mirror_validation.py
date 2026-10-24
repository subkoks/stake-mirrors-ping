"""Shared validation for configuration, discovery and actual socket destinations."""

import asyncio
import ipaddress
import math
import re
import socket
from urllib.parse import urlsplit, urlunsplit

from aiohttp.abc import AbstractResolver


def public_ip(value: str) -> str:
    address = ipaddress.ip_address(value)
    if not address.is_global or address.is_multicast or address.is_unspecified:
        raise ValueError("Destination must resolve exclusively to public addresses")
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        public_ip(str(address.ipv4_mapped))
    return str(address)


def normalize_hostname(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("Hostname must be a nonempty string without whitespace")
    try:
        host = value.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("Invalid IDN hostname") from exc
    try:
        return public_ip(host)
    except ValueError:
        # Numeric addresses may not fall through into the hostname path.
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError("Non-public address") from None
    if len(host) > 253 or "." not in host or host.endswith("."):
        raise ValueError("Expected a fully qualified public hostname")
    if any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in host.split(".")
    ):
        raise ValueError("Invalid hostname")
    if host.endswith((".localhost", ".local", ".internal", ".test", ".invalid")):
        raise ValueError("Local/reserved hostname is not supported")
    return host


def normalize_destination(domain: str, url: str) -> tuple[str, str]:
    host = normalize_hostname(domain)
    if (
        not isinstance(url, str)
        or any(c.isspace() or ord(c) < 32 for c in url)
        or "\\" in url
    ):
        raise ValueError("Invalid destination URL")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only HTTP and HTTPS destinations are supported")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Credentials in URLs are forbidden")
    if normalize_hostname(parsed.hostname) != host:
        raise ValueError("Mirror domain and URL hostname must agree")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError(
            "Mirror URLs must be origins without paths, queries or fragments"
        )
    port = parsed.port  # validates malformed/out-of-range ports
    if port == 0 or parsed.netloc.endswith(":"):
        raise ValueError("Invalid destination port")
    authority = f"[{host}]" if ":" in host else host
    if port is not None and port != (443 if parsed.scheme == "https" else 80):
        authority += f":{port}"
    return host, urlunsplit((parsed.scheme, authority, "", "", ""))


def validate_settings(
    rounds: object, timeout: object, concurrency: object
) -> tuple[int, float, int]:
    if type(rounds) is not int or not 1 <= rounds <= 20:
        raise ValueError("ping_rounds must be an integer from 1 to 20")
    if (
        not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or not math.isfinite(timeout)
        or not 0 < timeout <= 120
    ):
        raise ValueError(
            "timeout_seconds must be finite and greater than 0, at most 120"
        )
    if type(concurrency) is not int or not 1 <= concurrency <= 64:
        raise ValueError("concurrent_limit must be an integer from 1 to 64")
    return rounds, float(timeout), concurrency


class PublicResolver(AbstractResolver):
    """Validate every DNS answer used by aiohttp, rather than checking then re-resolving."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    async def resolve(
        self, host: str, port: int = 0, family: int = socket.AF_INET
    ) -> list:
        records = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(
                host, port, family=family, type=socket.SOCK_STREAM
            ),
            timeout=self.timeout,
        )
        answers = []
        for family_id, _, proto, _, sockaddr in records:
            address = public_ip(str(sockaddr[0]))
            record = {
                "hostname": host,
                "host": address,
                "port": port,
                "family": family_id,
                "proto": proto,
                "flags": socket.AI_NUMERICHOST,
            }
            if record not in answers:
                answers.append(record)
        if not answers:
            raise OSError("No DNS answers")
        return answers

    async def close(self) -> None:
        pass
