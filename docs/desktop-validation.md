# Desktop candidate validation

Candidate: 2.1.0. This is engineering evidence, not a published release or signing claim.

## Local Intel macOS

- CPython 3.13.16 + PyInstaller 6.22.3 production and separate fixture backends built from the lockfile.
- Frozen production binary: native curl/TLS loading, CA initialization, configuration, settings and SQLite commands outside the checkout.
- Electron 45.0.0 production .app, DMG and ZIP generated; unsigned, not notarized.
- Five packaged production scenarios: bundled selection despite invalid external preferences; settings persistence; About/redacted diagnostics and unsafe-link rejection; mocked update success/failure; missing-engine recovery without resetting settings.
- Eleven separate fixture scenarios cover progress/results, safe browser handoff, history across restart, cancel/restart, offline/empty/failure recovery, 150% scaling, keyboard focus and active-child shutdown, plus common startup/support checks.
- Readiness to enabled Start scan approximately 2.0–2.2 seconds in these local runs. These are warm engineering measurements, not a cold-start performance guarantee.
- 117 Python tests; 14 Node tests; Ruff lint/format, isort, mypy, wheel/sdist and full npm audit passed. No production accounts, tokens, VPN actions or live mirror scans used.

## CI qualification

[Native qualification run](https://github.com/subkoks/stake-mirrors-ping/actions/runs/40141972276) at `8c1a7f0` passed all four platform jobs: five production and eleven fixture scenarios per platform. Windows also passed reinstall-over-existing-app preservation. Both clean Ubuntu 22.04/24.04 installations passed four production scenarios; the read-only installed-engine mutation case was explicitly skipped there and covered in writable installations. The final inventory gate caught Linux package architecture labels (`amd64`/`x86_64`); its expected names were corrected and regression-tested. The final PR head must pass the complete workflow, including candidate assembly, before marking ready; see [PR #100 checks](https://github.com/subkoks/stake-mirrors-ping/pull/100/checks) for that authoritative result. CI installer launches use disposable paths containing spaces/non-ASCII characters. Clean Ubuntu containers separately assert that system Python/Node/Git are absent and install the actual DEB; the test controller is supplied externally and is not an application dependency.

Windows Server CI is not manual Windows 10/11 verification. Modern Mac runner launches are not macOS 13 hardware validation. Linux container namespace permissions are described in desktop-distribution.md; they do not prove every stock host policy. RPM distribution qualification, AppImage/FUSE integration and signed/notarized launch acceptance remain separate from installer generation.

## External gates

No new release/tag is published. Public release requires final candidate approval. macOS Developer ID/notarization and Windows publisher signing are not verified without separately authorized credentials. An unsigned engineering candidate must not be advertised as a frictionless public install on every OS.
