"""Explicit, preview-first refresh of the offline canonical mirror configuration."""

import argparse
import asyncio
import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp
import yaml

from .core.orchestrator import parse_mirrors
from .mirror_validation import PublicResolver, normalize_destination

SOURCE = "https://mirrorslist.playstake.io/mirror-list.json"
MAX_BYTES = 256 * 1024


def atomic_write(path: Path, text: str) -> None:
    """Replace one file on its own filesystem; an interruption preserves the old file."""
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def parse_source(data: object) -> list[dict[str, str]]:
    if not isinstance(data, list) or not data or len(data) > 2000:
        raise ValueError("Source must be a nonempty bounded list of HTTPS origins")
    result = {}
    for url in data:
        if not isinstance(url, str):
            raise ValueError("Source destinations must be strings")
        parsed = urlsplit(url)
        host, normalized = normalize_destination(parsed.hostname or "", url)
        if parsed.scheme != "https" or parsed.port not in (None, 443):
            raise ValueError("Discovered destinations must use standard HTTPS")
        result[host] = {"domain": host, "url": normalized}
    return list(result.values())


async def fetch_source() -> tuple[list[dict[str, str]], str]:
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(resolver=PublicResolver(10)),
        timeout=aiohttp.ClientTimeout(total=15),
        trust_env=False,
    ) as session:
        async with session.get(SOURCE, allow_redirects=False) as response:
            if response.status != 200:
                raise ValueError(
                    f"Discovery source returned HTTP {response.status}; configuration preserved"
                )
            raw = bytearray()
            async for chunk in response.content.iter_chunked(8192):
                raw.extend(chunk)
                if len(raw) > MAX_BYTES:
                    raise ValueError("Discovery response exceeds size limit")
    return parse_source(json.loads(raw)), datetime.now(UTC).isoformat()


def build_refresh(
    config_text: str, entries: list[dict[str, str]], previous: dict
) -> tuple[str, dict]:
    config = yaml.safe_load(config_text)
    existing = {m.domain: m for m in parse_mirrors(config)}
    incoming = {m["domain"]: m for m in entries}
    previous_domains = set(previous.get("listed_domains", []))
    # Refuse reductions and same-size substitutions, including against the first inventory.
    expected = previous_domains or set(existing)
    missing = sorted(expected - incoming.keys())
    added = sorted(incoming.keys() - existing.keys())
    retained = sorted(existing.keys() - incoming.keys())
    report = {
        "listed_count": len(incoming),
        "added": added,
        "retained_not_listed": retained,
        "missing_from_previous_source": missing,
        "removed": [],
        "requires_review": bool(missing),
    }
    lines = config_text.splitlines(keepends=True)
    start = next(
        (i for i, line in enumerate(lines) if line.rstrip() == "mirrors:"), None
    )
    if start is None:
        raise ValueError("Expected a top-level mirrors block")
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].strip()
            and not lines[i][0].isspace()
            and not lines[i].startswith("#")
        ),
        len(lines),
    )
    # Existing entries (including custom metadata/URLs) stay byte-for-byte intact.
    addition = "".join(
        f"  - domain: {incoming[d]['domain']}\n    url: {incoming[d]['url']}\n"
        for d in added
    )
    updated = (
        "".join(lines[:end]).rstrip() + "\n" + addition + "\n" + "".join(lines[end:])
    )
    parse_mirrors(yaml.safe_load(updated))
    report["configured_count"] = len(existing) + len(added)
    return updated, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument(
        "--snapshot", type=Path, default=Path("docs/mirrors/source-snapshot.yaml")
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply additions only when the source has not reduced",
    )
    args = parser.parse_args()
    try:
        # Use the exact selected path for both reads and writes.
        original = args.config.read_text(encoding="utf-8")
        previous = (
            yaml.safe_load(args.snapshot.read_text()) if args.snapshot.exists() else {}
        )
        entries, timestamp = asyncio.run(fetch_source())
        updated, report = build_refresh(original, entries, previous or {})
        recorded_digest = (previous or {}).get("config_sha256")
        report["config_changed_since_snapshot"] = bool(
            recorded_digest
            and recorded_digest != hashlib.sha256(original.encode()).hexdigest()
        )
        snapshot = {
            "source": SOURCE,
            "directory": "https://playstake.fans/",
            "retrieved_at": timestamp,
            "listed_count": len(entries),
            "listed_domains": [e["domain"] for e in entries],
            "config_sha256": hashlib.sha256(updated.encode()).hexdigest(),
            "diff": report,
        }
        print(yaml.safe_dump({"retrieved_at": timestamp, **report}, sort_keys=False))
        if args.apply:
            if report["requires_review"]:
                raise ValueError(
                    "Source reduction/substitution requires review; no files written"
                )
            if args.config.read_text(encoding="utf-8") != original:
                raise ValueError(
                    "Configuration changed during discovery; retry the preview"
                )
            args.snapshot.parent.mkdir(parents=True, exist_ok=True)
            # Snapshot first: a crash leaves either the old config or the complete new config.
            # Its digest allows detecting an interrupted two-file update.
            atomic_write(args.snapshot, yaml.safe_dump(snapshot, sort_keys=False))
            atomic_write(args.config, updated)
    except (ValueError, OSError, aiohttp.ClientError, TimeoutError) as exc:
        parser.exit(1, f"Refresh refused: {exc}\n")


if __name__ == "__main__":
    main()
