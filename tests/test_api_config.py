"Tests for the GUI config-update bridge (security allowlist / path guard)."

import sys
from pathlib import Path

# src/core/api.py bootstraps itself with `sys.path.insert` + `from core import ...`,
# so `src` must be importable as a top-level path for the import to succeed.
SRC_ROOT = str(Path(__file__).resolve().parent.parent / "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from src.core.api import ALLOWED_CONFIG_KEYS, _merge_config_update  # noqa: E402


def test_merge_applies_allowed_scalar_settings() -> None:
    existing = {"settings": {"ping_rounds": 3, "timeout_seconds": 10}}
    update = {"ping_rounds": 5, "timeout_seconds": 20}
    out = _merge_config_update(existing, update)
    assert out["settings"]["ping_rounds"] == 5
    assert out["settings"]["timeout_seconds"] == 20


def test_merge_ignores_disallowed_keys() -> None:
    existing = {"settings": {"ping_rounds": 3}, "mirrors": [{"domain": "x"}]}
    # Attempt to inject a malicious mirror and redirect the write target.
    update = {
        "config_path": "../../../.env",
        "mirrors": [{"domain": "evil.com", "url": "https://evil.com"}],
        "nordvpn": {"target_regions": ["Nowhere"]},
        "ping_rounds": 9,
    }
    out = _merge_config_update(existing, update)
    # Allowed key applied.
    assert out["settings"]["ping_rounds"] == 9
    # Nested structures untouched — no injection.
    assert out["mirrors"] == [{"domain": "x"}]
    assert "nordvpn" not in out


def test_merge_preserves_other_settings() -> None:
    existing = {"settings": {"ping_rounds": 3, "concurrent_limit": 16}}
    _merge_config_update(existing, {"timeout_seconds": 12})
    assert existing["settings"]["concurrent_limit"] == 16
    assert existing["settings"]["timeout_seconds"] == 12


def test_allowed_keys_are_the_expected_scalars() -> None:
    assert ALLOWED_CONFIG_KEYS == {"ping_rounds", "timeout_seconds", "concurrent_limit"}
