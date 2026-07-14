"""Tests for the GUI JSON-RPC bridge handlers (security-critical IPC).

Covers the real config write path (_patch_settings_block), run-scan
serialization, and handler dispatch / error paths. Complements
test_api_config.py (which covers the pure _merge_config_update allowlist).
"""

import json
import sys
from pathlib import Path

SRC_ROOT = str(Path(__file__).resolve().parent.parent / "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

import pytest  # noqa: E402

from src.core.api import (  # noqa: E402
    _patch_settings_block,
    handle_get_config,
    handle_run_scan,
    main,
)
from src.core.orchestrator import ScanResult  # noqa: E402
from src.models import MirrorConfig, PingResult  # noqa: E402


# --------------------------------------------------------------------------- #
# Real config write path (allowlist + path guard enforcement on disk)
# --------------------------------------------------------------------------- #
def test_patch_settings_block_applies_allowed_and_preserves_comments(
    tmp_path: Path,
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "settings:\n"
        "  ping_rounds: 3\n"
        "  timeout_seconds: 10  # keep me\n"
        "  concurrent_limit: 16\n"
        "mirrors:\n"
        "  - domain: a.com\n"
    )
    _patch_settings_block(
        cfg, {"ping_rounds": 5, "concurrent_limit": 8, "evil_key": "x"}
    )
    out = cfg.read_text()
    assert "ping_rounds: 5" in out
    assert "concurrent_limit: 8" in out
    # comment preserved
    assert "timeout_seconds: 10  # keep me" in out
    # disallowed key ignored (no injection)
    assert "evil_key" not in out


def test_patch_settings_block_noop_when_no_change(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("settings:\n  ping_rounds: 3\n")
    before = cfg.read_text()
    _patch_settings_block(cfg, {"timeout_seconds": 99})  # not in settings block
    assert cfg.read_text() == before


# --------------------------------------------------------------------------- #
# run-scan handler: success path serialization
# --------------------------------------------------------------------------- #
def test_handle_run_scan_serializes_scan_result(monkeypatch, capsys) -> None:
    mirror = MirrorConfig(domain="x.com", url="https://x.com")
    result = ScanResult(
        mirrors=[
            PingResult(
                mirror=mirror,
                is_up=True,
                tcp_latency_ms=10.0,
                https_latency_ms=20.0,
                ip_address="1.2.3.4",
                server_location="Earth",
                ssl_valid=True,
                http_status=200,
            )
        ],
        vpn_recommendations={},
        timestamp="2026-07-14T00:00:00",
        scan_id="scan-1",
    )

    async def fake_run_scan(config):  # noqa: ANN001
        return result

    monkeypatch.setattr("src.core.api.run_scan", fake_run_scan)

    handle_run_scan(json.dumps({"config_path": "config.yaml", "rounds": 1}))
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["scan_id"] == "scan-1"
    assert payload["mirrors"][0]["domain"] == "x.com"
    assert payload["mirrors"][0]["best_ms"] == 10.0


# --------------------------------------------------------------------------- #
# run-scan handler: error path (unknown key -> TypeError -> error JSON + exit)
# --------------------------------------------------------------------------- #
def test_handle_run_scan_reports_error_on_bad_config(monkeypatch, capsys) -> None:
    async def fake_run_scan(config):  # noqa: ANN001
        raise AssertionError("should not be called")

    monkeypatch.setattr("src.core.api.run_scan", fake_run_scan)

    with pytest.raises(SystemExit) as exc:
        handle_run_scan(json.dumps({"not_a_real_key": 1}))
    assert exc.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is False
    assert "error" in payload


# --------------------------------------------------------------------------- #
# get-config handler: loads project config successfully
# --------------------------------------------------------------------------- #
def test_handle_get_config_success(capsys) -> None:
    # config.yaml exists at project root; load_config falls back to it.
    handle_get_config()
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert "config" in payload


# --------------------------------------------------------------------------- #
# main() dispatch: unknown command -> error JSON + exit
# --------------------------------------------------------------------------- #
def test_main_unknown_command_errors(capsys, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["api.py", "frobnicate"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is False
    assert "Unknown command" in payload["error"]


def test_main_no_command_errors(capsys, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["api.py"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is False
