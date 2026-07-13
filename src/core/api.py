#!/usr/bin/env python3
"""JSON-RPC API server for GUI bridge."""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import OrchestratorConfig, run_scan
from history import HistoryDB


def print_json(data: dict) -> None:
    """Print JSON to stdout for Electron to parse."""
    print(json.dumps(data))
    sys.stdout.flush()


def handle_run_scan(args_json: str) -> None:
    """Handle run-scan command."""
    try:
        config_dict = json.loads(args_json)
        config = OrchestratorConfig(**config_dict)

        result = asyncio.run(run_scan(config))

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
        from core import load_config

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
    """Handle update-config command."""
    try:
        import yaml

        from core import load_config

        new_config = json.loads(args_json)
        config_path = new_config.get("config_path", "config.yaml")

        # Load existing config and merge
        existing = load_config(config_path)
        for key, value in new_config.items():
            if key != "config_path":
                existing[key] = value

        # Save back
        with open(config_path, "w") as f:
            yaml.dump(existing, f, default_flow_style=False)

        output = {"success": True}
        print_json(output)
    except Exception as e:
        print_json({"success": False, "error": str(e)})
        sys.exit(1)


def main() -> None:
    """Main entry point for JSON-RPC API."""
    if len(sys.argv) < 2:
        print_json({"success": False, "error": "No command specified"})
        sys.exit(1)

    command = sys.argv[1]
    args_json = sys.argv[2] if len(sys.argv) > 2 else "{}"

    if command == "run-scan":
        handle_run_scan(args_json)
    elif command == "get-history-stats":
        handle_get_history_stats(args_json)
    elif command == "get-config":
        handle_get_config()
    elif command == "update-config":
        handle_update_config(args_json)
    else:
        print_json({"success": False, "error": f"Unknown command: {command}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
