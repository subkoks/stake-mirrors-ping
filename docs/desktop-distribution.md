# Self-contained desktop distribution

Status: **2.1.0 candidate; not published**. v2.0.0 remains unchanged and requires external Python. This document describes the new architecture and its acceptance gates, not evidence that every gate has passed.

## Runtime and provenance

Electron 45.0.0 hosts the sandboxed renderer. A native PyInstaller 6.22.3 one-folder executable includes CPython 3.13.16, the locked application dependencies, CFFI/curl, Pydantic native extensions, SQLite, and CA certificates. Build-only hooks are pinned at 2026.9 in the `desktop` dependency group. Node 22.23.1 and uv 0.12.5 are CI tools, not end-user requirements.

Each backend is built natively on the same OS and architecture as its installer. The builder rejects mismatched OS, architecture, fixture flavor, or package version. `resources/backend/provenance.json` records the Python version, dependency lock digest, build environment, and collected-file hashes. License notices are copied alongside the backend. Hashes establish build-file integrity, not publisher authentication; signing changes native binary bytes and requires final-file checksums afterward.

Production bundles contain no fixture entry point. Test applications are explicitly marked through package metadata and use a separately frozen fixture backend. Packaged startup accepts the corresponding flavor only. Production never reads `python-path.txt` or `STAKE_PYTHON`, never falls back to PATH, and never installs/downloads runtime code. Development launches retain explicit interpreter discovery.

The backend's `health` command exercises frozen-runtime detection, architecture, package version, native curl loading, and CA initialization. The standard bridge commands and final payloads remain compatible. A separate `--stream` mode emits bounded JSON lines for measured completion counts; stderr is kept separate. Cancellation and shutdown terminate tracked children, and a newer scan cannot consume the old scan's events.

## Supported targets and evidence boundaries

| Target | Compatibility baseline | Validation design |
| --- | --- | --- |
| Windows x64 | Windows 10/11 (Electron floor) | Windows Server 2022 runner: NSIS silent install into a disposable Unicode path, installed-app launch, interactions; this does not establish manual Windows 10/11 desktop acceptance |
| macOS Intel | macOS 13+ | Native Intel runner; mount DMG read-only, copy into disposable Unicode path, launch and interact |
| macOS Apple Silicon | macOS 13+ | Native arm64 runner; same installed-app checks |
| Linux x64 | Ubuntu 22.04/24.04 desktop, glibc 2.35+ | Native Ubuntu 22.04 build, DEB extraction, Xvfb interactions; clean Ubuntu containers assert no Python and launch the production GUI with an external test driver |

Electron 44+ requires macOS 13. Native backend dependencies may impose additional requirements; candidate qualification must inspect/link-test those artifacts before confirming compatibility. Running a newer macOS CI image does not prove macOS 13 operation. Linux is not universally portable: build against the oldest supported glibc and validate actual dependencies. RPM is generated but is not qualified for a Fedora baseline until installer validation exists. AppImage generation does not prove FUSE integration on every desktop.

Tests distinguish built, launched, interaction-tested, installer-tested, and manual validation. The Linux container uses `--no-sandbox` only for disposable root automation; production app configuration keeps renderer sandboxing enabled. No user is instructed to disable OS protections.

## User data and upgrade behavior

Keep app ID `com.stakemirrors.ping`, product name, and Electron user-data location unchanged:

- macOS: `~/Library/Application Support/Stake Mirrors Ping`
- Windows: `%APPDATA%/Stake Mirrors Ping`
- Linux: `${XDG_CONFIG_HOME:-~/.config}/Stake Mirrors Ping`

`config.yaml` is copied only on first launch; `history.db` stays in user data. Upgrade/reinstall must preserve both. `support/` contains fixed diagnostic codes and a bounded log. The copyable diagnostic summary deliberately excludes paths, environment variables, account tokens, configuration and scan results. No telemetry or background startup is added.

## Signing prerequisites

Unsigned engineering builds are allowed. They are not a frictionless public-distribution claim.

For macOS direct distribution: an Apple Developer Program account, Developer ID Application identity and Team ID, approved CI certificate access, and notarization authentication (prefer App Store Connect API key ID/issuer/private-key reference or an approved keychain profile). Nested Python executables/libraries must be signed consistently before the outer app. Verify hardened runtime, notarization acceptance and stapled tickets. Current entitlements permit JIT for Electron; signing/notarization cannot be reported as verified until those credentials are supplied through an approved mechanism.

Windows requires an approved Authenticode certificate/signing service and timestamping. electron-builder supports certificate or managed signing integration; do not assume the optional signing dependencies omitted from unsigned builds are ready. Validate the selected provider and its dependencies when credentials are available. Do not embed keys or certificate passwords in config. Signing is publisher identity, while SmartScreen reputation remains separate.

No paid account, credential upload, global installation, or host-security change is performed by the engineering workflow.

## Updates

Help & About offers an explicit Check for updates action. It reads the fixed GitHub release endpoint with bounded response size/time, validates stable release metadata, and compares numeric versions. Official downloads open only the fixed repository release page. No custom executable downloader, updater feed, automatic installation, or new hosting is introduced. A failed check provides retry guidance and leaves the current app/data intact.

## Build and verification (developers)

```sh
uv sync --locked --group desktop --python 3.13.16
uv run --python 3.13.16 --locked --group desktop python scripts/build_backend.py
uv run --python 3.13.16 --locked python scripts/test_frozen_backend.py packaging/output/production/darwin-x64/stake-backend/stake-backend
cd gui
npm ci --omit=optional --registry=https://registry.npmjs.org
npm test
npm run build -- --publish never
```

Use the matching target path on each native OS. Do not cross-package a Python executable. `scripts/install_desktop_candidate.py` installs/extracts only into temporary directories; it does not touch host Applications or uninstall existing software. Fixture builds use `build_backend.py --fixture` and `STAKE_DESKTOP_TEST=1` when packaging into a separate output directory.

## Candidate and release gate

The build workflow produces exactly nine named installers/archives plus final-byte checksums and a manifest. It uploads CI candidate artifacts only; it does not create a tag or public release. Candidate artifacts have a 14-day retention period and may need regeneration before release approval.

Before publication: verify source commit/tree, all four target jobs, native runtime and architecture, installer/interaction evidence, remaining platform limits, signing status, and nine final asset names/digests. Prepare a new release instead of replacing v2.0.0. A separate explicit user approval is required before creating the tag and publishing binaries. The manually invoked `Prepare approved release draft` workflow never creates a tag or publishes; it verifies an existing tag, downloads the exact-source successful candidate, checks every final file digest/name/size, and uploads only a draft. Final publication remains a separate explicit approval step. Draft preparation must verify an existing approved tag and successful build at that exact SHA; keep the release draft until every asset/check is complete. Never publish an empty release, move tags, or treat checksums as signatures.
