# Changelog

## [2.1.0] - 2026-10-25

- Bundle a native Python 3.13.16 scan engine with the Electron desktop application; no end-user interpreter or package installation.
- Preserve saved configuration/history while ignoring obsolete external interpreter preferences in packaged apps.
- Add measured scan progress, simpler controls, safe configured-mirror opening, error recovery, About/support diagnostics and manual update checks.
- Build each backend on its own OS/architecture; add packaged interaction and installer-path checks for all four desktop targets.
- Correct Electron 45 minimum macOS version to 13 and document the Linux baseline.
- Publish nine self-contained desktop installers/archives with final-file checksums and a source manifest; builds are unsigned and macOS is not notarized.

## [2.0.0] - 2026-10-24

- Upgrade Electron 33.4.11 to stable supported 43.8.3 and electron-builder 25.1.8 to 26.18.0; resolve the full npm audit without overrides.
- Validate IPC sender/payloads, minimize preload exposure, and clean up all Python children on close/quit while allowing macOS window reactivation.
- Validate external Python versions/dependency minimums, support an absolute interpreter preference, and display actionable prerequisite errors at startup.
- Add offline rendered Electron and packaged macOS startup regression checks; require an explicit compatible Node version and GUI audit in CI.

- Refresh the offline inventory from PlayStake public JSON; retain absent/custom entries and record provenance.
- Add explicit preview-first, guarded, atomic mirror refresh.
- Validate mirror destinations and public DNS; prevent credential redirects and mismatched trusted hosts.
- Classify local reachability honestly and rank by HTTP latency consistently across CLI/GUI/exports.
- Honor configured concurrency, bound DNS waits, deduplicate GeoIP, and fix GUI stop/restart ownership.
- Preserve SQLite rows with additive status metadata; historical best timings remain legacy measurements.
- Restore tracked GUI manifests, packaged resource paths/config inclusion, reproducible CI and dependency auditing.


All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-07-14

### Fixed
- **Stored XSS** in GUI `renderer.js` — mirror/GeoIP/NordVPN/history data was injected via `innerHTML`; now built with `textContent`. Added CSP + renderer sandbox + navigation guard in `index.html`/`main.js`.
- **Arbitrary file write / path traversal** in `core/api.py update-config` — `config_path` came from input and all keys were merged; now pinned to `config.yaml` and limited to an allowlist of scalar settings.
- **SQL injection** in `history.py` — `hours`/`days` were f-string-interpolated into the query modifier; now coerced to `int` with a non-negative bound check.
- **Live dashboard GeoIP refresh was dead code** — it checked a non-existent `status` field and read wrong coordinate keys (`lat`/`lon` vs `location.latitude`/`longitude`), so new IPs never got GeoIP in `--live`. Now uses the shared `_apply_geoip` helper.
- **`ssl_valid` defaulted to `True` on any non-TLS failure** (timeout/connection error) — now correctly `False` since TLS was never validated.
- GUI CSP used `style-src 'self'`, which blocked the inline `<style>` block and left the entire UI unstyled; now allows `'unsafe-inline'` for styles.
- GUI "Save Settings" sent `{rounds, timeout}` while the API allowlist expected `ping_rounds`/`timeout_seconds`, so saving was a silent no-op; renderer now maps to the config schema keys.
- **DB path drift** — GUI `run_scan` wrote to cwd-relative `history.db`; now uses the project-root `DB_PATH` so GUI and CLI share the same database.
- Removed dead/misleading `geoip:` config block (wrong provider, insecure `http://` URL).
- Concurrent GeoIP lookups (was 16 sequential calls).
- `__import__('datetime')` in the watch loop replaced with a module import.

### Changed
- Dropped unused `geoip2` and `requests` dependencies (supply-chain surface).
- Lowered `pytest` dev floor `>=9.0.3` → `>=8.0` (the 9.x floor was unresolvable on PyPI).
- Regenerated `uv.lock` after dependency changes.

### Added
- Regression tests for GeoIP response shape, SSL-validity semantics, and history SQL validation.

## [1.0.0] - 2026-02-21

### Added
- Initial release of Stake Mirrors Ping tool
- Concurrent testing of 16 Stake mirror sites
- TCP, HTTPS, and DNS latency measurements
- GeoIP lookup integration for server location detection
- NordVPN region recommendations
- Stake API integration with curl_cffi (Cloudflare bypass)
- Live dashboard with auto-refresh capability
- SQLite-based history tracking with uptime statistics
- Rich CLI with color-coded sorted tables
- JSON and CSV export functionality
- Configurable via YAML file
- Support for $0 Dice bet latency benchmarking
- Command-line options for customization (rounds, timeout, etc.)
- MIT License
- Contributing guidelines (CONTRIBUTING.md)
- GitHub Actions CI/CD workflow for automated testing
- Issue/PR templates, security policy (SECURITY.md), Code of Conduct
- Dependabot configuration
- EditorConfig for consistent coding style
- Professional badges to README
- Pre-commit hooks for ruff, mypy, and code quality checks
- `geoip2` dependency to pyproject.toml

### Changed
- Upgraded Python target from 3.12 to 3.13
- Updated development status from Beta to Production/Stable
- Updated GitHub Actions to use Python 3.13
- Improved CI workflow with proper pytest integration
- Enhanced security scanning with Safety CLI
- Fixed 92 ruff linting issues
- Fixed 13 mypy type errors
- Updated pip from 25.3 to 26.1.2 (security fixes)
- Simplified requirements.txt to core dependencies only
- Added ruff and mypy to dev dependency groups
- Type annotations for optional aiohttp sessions
- Unused loop variables in reporter.py
- Whitespace issues in nordvpn.py
- Type annotations in history.py, dns_resolver.py, dashboard.py
- Config loading to handle empty YAML files safely
- HistoryDB path handling for None values
- Removed deprecated WebSocket testing (Stake has no WS endpoint)

## [0.2.0] - 2026-02-20

### Added
- Parallel API tests for improved performance
- curl_cffi integration for Cloudflare TLS fingerprint bypass
- Live dashboard mode with `rich.live`
- SQLite database for persistent history tracking

## [0.1.0] - 2026-02-19

### Added
- Initial implementation
- Basic mirror ping functionality
- Multi-round testing support
- Configuration file support

[Unreleased]: https://github.com/subkoks/stake-mirrors-ping/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/subkoks/stake-mirrors-ping/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/subkoks/stake-mirrors-ping/releases/tag/v1.0.0
[0.2.0]: https://github.com/subkoks/stake-mirrors-ping/releases/tag/v0.2.0
[0.1.0]: https://github.com/subkoks/stake-mirrors-ping/releases/tag/v0.1.0
