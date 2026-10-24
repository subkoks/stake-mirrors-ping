#!/usr/bin/env python3
"""JSON-RPC API server for GUI bridge."""

import asyncio
import json
import platform
import ssl
import sys
from importlib.metadata import version
from pathlib import Path

# Import the project's `src` package in a way that works both when this file is
# imported as `src.core.api` (tests) and when run as a script
# (`python src/core/api.py`, as the Electron GUI does). In script mode the
# project root is added to sys.path so `src` resolves as a package; the
# relative imports below then resolve correctly.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.core import OrchestratorConfig, run_scan
    from src.history import HistoryDB
else:
    from ..history import HistoryDB
    from . import OrchestratorConfig, run_scan


from src.mirror_update import atomic_write
from src.mirror_validation import validate_settings

STREAM = False


def print_json(data: dict) -> None:
    """Print JSON to stdout for Electron to parse."""
    print(json.dumps({"type": "result", "data": data} if STREAM else data))
    sys.stdout.flush()


def handle_run_scan(args_json: str) -> None:
    """Handle run-scan command."""
    try:
        config_dict = json.loads(args_json)
        config = OrchestratorConfig(**config_dict)

        def progress(stage: str, completed: int, total: int) -> None:
            print(
                json.dumps(
                    {
                        "type": "progress",
                        "stage": stage,
                        "completed": completed,
                        "total": total,
                    }
                ),
                flush=True,
            )

        result = asyncio.run(
            run_scan(config, progress=progress) if STREAM else run_scan(config)
        )

        # Convert to dict for JSON serialization
        output = {
            "success": True,
            "scan_id": result.scan_id,
            "timestamp": result.timestamp,
            "mirrors": [
                {
                    "domain": r.mirror.domain,
                    "url": r.mirror.url,
                    "is_up": r.is_up,
                    "reachability": r.reachability,
                    "application_status": r.application_status,
                    "http_status": r.http_status,
                    "error": r.error,
                    "ip_address": r.ip_address,
                    "server_location": r.server_location,
                    "tcp_ms": r.tcp_latency_ms,
                    "https_ms": r.https_latency_ms,
                    "api_ms": r.api_latency_ms,
                    "best_ms": r.best_latency_ms,
                }
                for r in result.mirrors
            ],
            "vpn_recommendations": {
                domain: [
                    {
                        "vpn_hostname": rec.vpn_server.hostname,
                        "vpn_city": rec.vpn_server.city,
                        "vpn_country": rec.vpn_server.country,
                        "estimated_total_ms": rec.estimated_latency_ms,
                    }
                    for rec in recs
                ]
                for domain, recs in result.vpn_recommendations.items()
            },
        }
        print_json(output)
    except Exception as e:
        print_json({"success": False, "error": str(e)})
        sys.exit(1)


def handle_get_history_stats(args_json: str) -> None:
    """Handle get-history-stats command."""
    try:
        options = json.loads(args_json) if args_json else {}
        domain = options.get("domain")
        hours = options.get("hours", 24)

        with HistoryDB() as db:
            stats = db.get_uptime_stats_serialized(domain, hours)

        output = {
            "success": True,
            "stats": [s.model_dump() for s in stats],
        }
        print_json(output)
    except Exception as e:
        print_json({"success": False, "error": str(e)})
        sys.exit(1)


def handle_get_config() -> None:
    """Handle get-config command."""
    try:
        from src.core import load_config

        config = load_config()
        output = {
            "success": True,
            "config": config,
        }
        print_json(output)
    except Exception as e:
        print_json({"success": False, "error": str(e)})
        sys.exit(1)


def handle_update_config(args_json: str) -> None:
    """Handle update-config command.

    Security: the config path is restricted to the project-root config.yaml and
    cannot be pointed at an arbitrary file (path traversal / arbitrary write).
    Only known scalar settings keys are merged; nested structures (mirrors,
    nordvpn, settings) are ignored to avoid injecting untrusted content.
    """
    new_config = json.loads(args_json)
    # Reject any attempt to redirect the write target.
    requested_path = new_config.get("config_path")
    if requested_path is not None and requested_path != "config.yaml":
        print_json(
            {
                "success": False,
                "error": "Only the project config.yaml can be updated",
            }
        )
        sys.exit(1)

    config_path = "config.yaml"
    # Resolve relative to project root so the GUI (spawned from gui/) writes the
    # correct file. load_config already falls back to the project root for reads.
    project_root = Path(__file__).parent.parent.parent
    import os

    resolved_path = Path(os.environ.get("STAKE_DATA_DIR", project_root)) / config_path

    # Patch only the allowed scalar settings, preserving comments, key order,
    # and the rest of the file. Rewriting the whole YAML (yaml.dump) would strip
    # the security notes and reorder keys, so we edit the `settings:` block
    # line-by-line instead.
    updates = {k: new_config[k] for k in ALLOWED_CONFIG_KEYS if k in new_config}
    if updates:
        _patch_settings_block(resolved_path, updates)

    output = {"success": True}
    print_json(output)


# Allowlist of scalar settings that the GUI may change. Nested structures
# (mirrors, nordvpn) are intentionally excluded to prevent injecting content.
ALLOWED_CONFIG_KEYS = {"ping_rounds", "timeout_seconds", "concurrent_limit"}


def _patch_settings_block(path: Path, updates: dict) -> None:
    """Patch scalar settings inside the ``settings:`` block of ``path`` in place.

    Only lines matching an allowed key (indented under ``settings:``) are
    rewritten; comments, ordering, and all other content are preserved. The
    file is rewritten only if an actual change was made.
    """
    text = path.read_text()
    import yaml

    settings = (yaml.safe_load(text) or {}).get("settings", {})
    values = {
        **settings,
        **{k: v for k, v in updates.items() if k in ALLOWED_CONFIG_KEYS},
    }
    validate_settings(
        values.get("ping_rounds", 3),
        values.get("timeout_seconds", 10),
        values.get("concurrent_limit", 16),
    )
    lines = text.splitlines()
    out: list[str] = []
    changed = False
    in_settings = False
    for line in lines:
        stripped = line.strip()
        if not in_settings:
            if stripped == "settings:":
                in_settings = True
            out.append(line)
            continue
        # A less-indented (or non-indented) line ends the settings block.
        if line and not line[0].isspace():
            in_settings = False
            out.append(line)
            continue
        matched = False
        for key, value in updates.items():
            if stripped.startswith(f"{key}:"):
                indent = line[: len(line) - len(line.lstrip())]
                new_line = f"{indent}{key}: {value}"
                if new_line != line:
                    changed = True
                out.append(new_line)
                matched = True
                break
        if not matched:
            out.append(line)
    if changed:
        atomic_write(path, "\n".join(out) + "\n")


def _merge_config_update(existing: dict, new_config: dict) -> dict:
    """Apply a GUI config update to an existing config dict (pure, no I/O).

    Only keys in ``ALLOWED_CONFIG_KEYS`` are written, and they are placed under
    the ``settings`` mapping. Anything else (including ``config_path`` and
    nested structures) is ignored. Returns the mutated ``existing`` dict.
    """
    settings = existing.setdefault("settings", {})
    for key, value in new_config.items():
        if key in ALLOWED_CONFIG_KEYS:
            settings[key] = value
    return existing


def main() -> None:
    """Main entry point for JSON-RPC API."""
    global STREAM
    STREAM = "--stream" in sys.argv[1:]
    if STREAM:
        sys.argv.remove("--stream")
    if len(sys.argv) < 2:
        print_json({"success": False, "error": "No command specified"})
        sys.exit(1)

    command = sys.argv[1]
    args_json = sys.argv[2] if len(sys.argv) > 2 else "{}"

    if command == "health":
        import certifi
        from curl_cffi import Curl

        ssl.create_default_context(cafile=certifi.where())
        curl = Curl()
        try:
            native = curl.version().decode("utf-8", errors="replace")
        finally:
            curl.close()
        print_json(
            {
                "success": True,
                "protocol": 1,
                "version": version("stake-mirrors-ping"),
                "python": platform.python_version(),
                "architecture": {
                    "AMD64": "x64",
                    "x86_64": "x64",
                    "aarch64": "arm64",
                }.get(platform.machine(), platform.machine()),
                "frozen": bool(getattr(sys, "frozen", False)),
                "native_tls": native,
            }
        )
    elif command == "run-scan":
        handle_run_scan(args_json)
    elif command == "get-history-stats":
        handle_get_history_stats(args_json)
    elif command == "get-config":
        handle_get_config()
    elif command == "update-config":
        try:
            handle_update_config(args_json)
        except (ValueError, OSError, TypeError) as exc:
            print_json({"success": False, "error": str(exc)})
            sys.exit(1)
    else:
        print_json({"success": False, "error": f"Unknown command: {command}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
