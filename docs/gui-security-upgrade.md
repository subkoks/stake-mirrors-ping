# GUI dependency security upgrade — 2026-10-24

Baseline: PR #94 at `bc4f5034b405d58e78da1736b1526b15d50eaaa9`. Audit command: `npm audit --package-lock-only --registry=https://registry.npmjs.org --json`, including development dependencies. The committed lockfile reported **18 high and one critical affected-package finding**. These are npm aggregate package counts, not 19 distinct vulnerabilities. Individual advisory records and exact affected/fixed ranges are below.

## Version choice and migration review

Electron 33.4.11 → **43.8.3**, electron-builder 25.1.8 → **26.18.0**, exact versions locked. Both releases are published stable (GitHub `prerelease: false`). Electron 43 is one of the three supported stable lines as of this verification; using its latest minor retains macOS 12 support and avoids the additional 44/45 platform/API changes (44 requires macOS 13 and removes 32-bit Windows/Linux ARM builds). This upgrade raises the app minimum from the older Electron runtime to macOS 12; the package metadata now states that minimum. Reassess support before future releases.

Sources: [Electron 43.8.3 release](https://github.com/electron/electron/releases/tag/v43.8.3), [support policy](https://www.electronjs.org/docs/latest/tutorial/electron-timelines), [breaking changes](https://www.electronjs.org/docs/latest/breaking-changes), [builder 26.18.0 release](https://github.com/electron-userland/electron-builder/releases/tag/electron-builder%4026.18.0).

Electron packaging and `@electron/rebuild` 4.2.1 require Node **>=22.12.0**. Local Node is **22.23.1**, also pinned in desktop CI. Electron embeds its own Node runtime, separate from the build host. No production native Node modules are declared. The sandboxed preload requires only `electron`; it does not use removed `remote`, Node integration, deprecated new-window handling, native addons, clipboard/capture APIs, or ASAR file descriptors passed to external processes. Python resources remain outside ASAR. Builder 26 changes native-rebuild internals and installer/archive handling; fresh platform packaging is required.

The selected Electron/builder/Playwright versions are stable. Inspection also found the parent's optional Windows signing branch (`electron-winstaller` → `@electron/windows-sign` → `postject@1.0.0-alpha.6`), which has no stable postject release. Unsigned builds do not use that optional Squirrel signing plugin. Clean installation therefore uses `--omit=optional`, enforced by the project npm config; the installed dependency graph is checked to contain no prerelease packages. The lockfile still describes the parent's optional dependency metadata. Full-graph audits explicitly include optional and development dependencies, so this omission does not hide audit findings. Signing is outside this task. No dependency overrides, audit exceptions or forced audit fixes were used. Playwright is an exact-pinned developer-only dependency for offline rendered Electron tests, not a packaged runtime dependency.

## Affected package paths and remediation

Paths are shortest resolved baseline paths per affected installed version. Runtime exposure does not imply exploitability in this application: remote navigation is denied and the renderer is sandboxed. Build/install dependencies still parse archives, XML, YAML and download metadata and are part of the supply-chain boundary.

| Package | Baseline versions and dependency paths | Exposure | Remediation/new resolved versions |
| --- | --- | --- | --- |
| `@electron/rebuild` | `3.6.1`: electron-builder → app-builder-lib → @electron/rebuild | Build/install tooling | 4.2.1; upgraded fixed parent and compatible transitive resolution |
| `@xmldom/xmldom` | `0.9.10`: electron-builder → app-builder-lib → @electron/osx-sign → plist → @xmldom/xmldom | Build/install tooling | 0.8.15; upgraded fixed parent and compatible transitive resolution |
| `app-builder-lib` | `25.1.8`: electron-builder → app-builder-lib | Build/install tooling; generated AppImage/update helper risk depends on packaging/use (no updater API used here) | 26.18.0; upgraded fixed parent and compatible transitive resolution |
| `brace-expansion` | `1.1.16`: electron-builder → app-builder-lib → @electron/universal → @electron/asar → minimatch → brace-expansion; `2.1.2`: electron-builder → app-builder-lib → @electron/universal → minimatch → brace-expansion; `5.0.7`: electron-builder → app-builder-lib → minimatch → brace-expansion | Build/install tooling | 1.1.21, 2.1.7, 5.0.12; upgraded fixed parent and compatible transitive resolution |
| `builder-util` | `25.1.7`: electron-builder → builder-util | Build/install tooling | 26.16.0; upgraded fixed parent and compatible transitive resolution |
| `builder-util-runtime` | `9.2.10`: electron-builder → builder-util-runtime | Build/install tooling; generated AppImage/update helper risk depends on packaging/use (no updater API used here) | 9.7.0; upgraded fixed parent and compatible transitive resolution |
| `cacache` | `16.1.3`: electron-builder → app-builder-lib → @electron/rebuild → node-gyp → make-fetch-happen → cacache | Build/install tooling | Removed from resolved graph; upgraded fixed parent and compatible transitive resolution |
| `dmg-builder` | `25.1.8`: electron-builder → dmg-builder | Build/install tooling | 26.18.0; upgraded fixed parent and compatible transitive resolution |
| `electron` | `33.4.11`: electron | Packaged Electron runtime; some APIs require specific platform/features | 43.8.3; upgraded fixed parent and compatible transitive resolution |
| `electron-builder` | `25.1.8`: electron-builder | Build/install tooling | 26.18.0; upgraded fixed parent and compatible transitive resolution |
| `electron-builder-squirrel-windows` | `25.1.8`: electron-builder → app-builder-lib → electron-builder-squirrel-windows | Build/install tooling | 26.18.0; upgraded fixed parent and compatible transitive resolution |
| `electron-publish` | `25.1.7`: electron-builder → app-builder-lib → electron-publish | Build/install tooling | 26.18.0; upgraded fixed parent and compatible transitive resolution |
| `extract-zip` | `2.0.1`: electron → extract-zip | Build/install tooling | Removed from resolved graph; upgraded fixed parent and compatible transitive resolution |
| `http-cache-semantics` | `4.2.0`: electron → @electron/get → got → cacheable-request → http-cache-semantics | Build/install tooling | 4.3.0; upgraded fixed parent and compatible transitive resolution |
| `ip-address` | `10.2.0`: electron-builder → app-builder-lib → @electron/rebuild → node-gyp → make-fetch-happen → socks-proxy-agent → socks → ip-address | Build/install tooling | Removed from resolved graph; upgraded fixed parent and compatible transitive resolution |
| `js-yaml` | `4.3.0`: electron-builder → app-builder-lib → js-yaml | Build/install tooling | 4.3.2; upgraded fixed parent and compatible transitive resolution |
| `make-fetch-happen` | `10.2.1`: electron-builder → app-builder-lib → @electron/rebuild → node-gyp → make-fetch-happen | Build/install tooling | Removed from resolved graph; upgraded fixed parent and compatible transitive resolution |
| `node-gyp` | `9.4.1`: electron-builder → app-builder-lib → @electron/rebuild → node-gyp | Build/install tooling | 12.4.0; upgraded fixed parent and compatible transitive resolution |
| `tar` | `6.2.1`: electron-builder → app-builder-lib → tar | Build/install tooling | 7.5.22; upgraded fixed parent and compatible transitive resolution |

## Individual advisory evidence

Ranges below come from npm audit and public GitHub advisory metadata retrieved for this review. A dash means no patched version was supplied for that affected range; removal or replacement by the fixed parent eliminates that dependency path. Multiple rows can refer to different affected release lines of the same advisory. Aggregate-only parent findings inherit the individual advisories listed here.

| Package | Severity | Advisory | npm affected range | GitHub affected range → first patched |
| --- | --- | --- | --- | --- |
| `@xmldom/xmldom` | high | [GHSA-6mj3-qw4j-hgrw](https://github.com/advisories/GHSA-6mj3-qw4j-hgrw) | `>=0.9.0-beta.1 <=0.9.11` | `>= 0.9.0-beta.1, <= 0.9.11` → `0.9.12` |
| `@xmldom/xmldom` | high | [GHSA-g53g-w8rj-fmg7](https://github.com/advisories/GHSA-g53g-w8rj-fmg7) | `>=0.9.0-beta.9 <=0.9.10` | `>= 0.9.0-beta.9, <= 0.9.10` → `0.9.11` |
| `@xmldom/xmldom` | high | [GHSA-w2rr-34g9-rvrj](https://github.com/advisories/GHSA-w2rr-34g9-rvrj) | `>=0.9.0 <=0.9.10` | `>= 0.9.0, <= 0.9.10` → `0.9.11`; `>= 0.7.0, <= 0.8.13` → `0.8.14` |
| `@xmldom/xmldom` | high | [GHSA-4w3w-2rp5-g8jm](https://github.com/advisories/GHSA-4w3w-2rp5-g8jm) | `>=0.9.0 <=0.9.10` | `>= 0.9.0, <= 0.9.10` → `0.9.11`; `>= 0.7.0, <= 0.8.13` → `0.8.14` |
| `@xmldom/xmldom` | high | [GHSA-c7q8-3ch8-vqpv](https://github.com/advisories/GHSA-c7q8-3ch8-vqpv) | `>=0.9.0 <=0.9.11` | `>= 0.7.0, <= 0.8.14` → `0.8.15`; `>= 0.9.0, <= 0.9.11` → `0.9.12` |
| `@xmldom/xmldom` | high | [GHSA-27p8-2357-5qqv](https://github.com/advisories/GHSA-27p8-2357-5qqv) | `>=0.9.0 <=0.9.11` | `>= 0.7.0, <= 0.8.14` → `0.8.15`; `>= 0.9.0, <= 0.9.11` → `0.9.12` |
| `@xmldom/xmldom` | high | [GHSA-3px3-54cx-rmw9](https://github.com/advisories/GHSA-3px3-54cx-rmw9) | `>=0.9.0 <=0.9.11` | `>= 0.9.0, <= 0.9.11` → `0.9.12` |
| `@xmldom/xmldom` | high | [GHSA-vr34-hp96-76pp](https://github.com/advisories/GHSA-vr34-hp96-76pp) | `>=0.9.10 <=0.9.11` | `>= 0.9.10, <= 0.9.11` → `0.9.12` |
| `@xmldom/xmldom` | high | [GHSA-8344-3jmq-59r6](https://github.com/advisories/GHSA-8344-3jmq-59r6) | `>=0.9.0 <=0.9.11` | `>= 0.7.0, <= 0.8.14` → `0.8.15`; `>= 0.9.0, <= 0.9.11` → `0.9.12` |
| `@xmldom/xmldom` | high | [GHSA-965w-775f-mr7g](https://github.com/advisories/GHSA-965w-775f-mr7g) | `>=0.9.0 <=0.9.11` | `>= 0.7.0, <= 0.8.14` → `0.8.15`; `>= 0.9.0, <= 0.9.11` → `0.9.12` |
| `@xmldom/xmldom` | high | [GHSA-93r5-fhx6-vmg9](https://github.com/advisories/GHSA-93r5-fhx6-vmg9) | `>=0.9.0 <=0.9.11` | `>= 0.7.0, <= 0.8.14` → `0.8.15`; `>= 0.9.0, <= 0.9.11` → `0.9.12` |
| `app-builder-lib` | high | [GHSA-7g7r-gx96-252g](https://github.com/advisories/GHSA-7g7r-gx96-252g) | `<26.15.0` | `< 26.15.0` → `26.15.0` |
| `brace-expansion` | high | [GHSA-mh99-v99m-4gvg](https://github.com/advisories/GHSA-mh99-v99m-4gvg) | `<1.1.17` | `>= 4.0.0, < 5.0.8` → `5.0.8`; `>= 3.0.0, < 3.0.3` → `3.0.3`; `>= 2.0.0, < 2.1.3` → `2.1.3`; `< 1.1.17` → `1.1.17` |
| `brace-expansion` | high | [GHSA-mh99-v99m-4gvg](https://github.com/advisories/GHSA-mh99-v99m-4gvg) | `>=2.0.0 <2.1.3` | `>= 4.0.0, < 5.0.8` → `5.0.8`; `>= 3.0.0, < 3.0.3` → `3.0.3`; `>= 2.0.0, < 2.1.3` → `2.1.3`; `< 1.1.17` → `1.1.17` |
| `brace-expansion` | high | [GHSA-mh99-v99m-4gvg](https://github.com/advisories/GHSA-mh99-v99m-4gvg) | `>=4.0.0 <5.0.8` | `>= 4.0.0, < 5.0.8` → `5.0.8`; `>= 3.0.0, < 3.0.3` → `3.0.3`; `>= 2.0.0, < 2.1.3` → `2.1.3`; `< 1.1.17` → `1.1.17` |
| `brace-expansion` | high | [GHSA-rgw5-rvv9-x895](https://github.com/advisories/GHSA-rgw5-rvv9-x895) | `>=4.0.0 <5.0.9` | `< 1.1.18` → `1.1.18`; `>= 2.0.0, < 2.1.4` → `2.1.4`; `>= 3.0.0, < 3.0.6` → `3.0.6`; `>= 4.0.0, < 5.0.9` → `5.0.9` |
| `brace-expansion` | high | [GHSA-rgw5-rvv9-x895](https://github.com/advisories/GHSA-rgw5-rvv9-x895) | `>=2.0.0 <2.1.4` | `< 1.1.18` → `1.1.18`; `>= 2.0.0, < 2.1.4` → `2.1.4`; `>= 3.0.0, < 3.0.6` → `3.0.6`; `>= 4.0.0, < 5.0.9` → `5.0.9` |
| `brace-expansion` | high | [GHSA-rgw5-rvv9-x895](https://github.com/advisories/GHSA-rgw5-rvv9-x895) | `<1.1.18` | `< 1.1.18` → `1.1.18`; `>= 2.0.0, < 2.1.4` → `2.1.4`; `>= 3.0.0, < 3.0.6` → `3.0.6`; `>= 4.0.0, < 5.0.9` → `5.0.9` |
| `brace-expansion` | high | [GHSA-qhr7-859c-m2p7](https://github.com/advisories/GHSA-qhr7-859c-m2p7) | `<1.1.20` | `>= 4.0.0, < 5.0.11` → `5.0.11`; `>= 3.0.0, < 3.0.8` → `3.0.8`; `>= 2.0.0, < 2.1.6` → `2.1.6`; `< 1.1.20` → `1.1.20` |
| `brace-expansion` | high | [GHSA-qhr7-859c-m2p7](https://github.com/advisories/GHSA-qhr7-859c-m2p7) | `>=2.0.0 <2.1.6` | `>= 4.0.0, < 5.0.11` → `5.0.11`; `>= 3.0.0, < 3.0.8` → `3.0.8`; `>= 2.0.0, < 2.1.6` → `2.1.6`; `< 1.1.20` → `1.1.20` |
| `brace-expansion` | high | [GHSA-qhr7-859c-m2p7](https://github.com/advisories/GHSA-qhr7-859c-m2p7) | `>=4.0.0 <5.0.11` | `>= 4.0.0, < 5.0.11` → `5.0.11`; `>= 3.0.0, < 3.0.8` → `3.0.8`; `>= 2.0.0, < 2.1.6` → `2.1.6`; `< 1.1.20` → `1.1.20` |
| `brace-expansion` | high | [GHSA-6j4f-fj2g-mc7p](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p) | `<1.1.19` | `>= 4.0.0, < 5.0.10` → `5.0.10`; `>= 3.0.0, < 3.0.7` → `3.0.7`; `>= 2.0.0, < 2.1.5` → `2.1.5`; `< 1.1.19` → `1.1.19` |
| `brace-expansion` | high | [GHSA-6j4f-fj2g-mc7p](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p) | `>=2.0.0 <2.1.5` | `>= 4.0.0, < 5.0.10` → `5.0.10`; `>= 3.0.0, < 3.0.7` → `3.0.7`; `>= 2.0.0, < 2.1.5` → `2.1.5`; `< 1.1.19` → `1.1.19` |
| `brace-expansion` | high | [GHSA-6j4f-fj2g-mc7p](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p) | `>=4.0.0 <5.0.10` | `>= 4.0.0, < 5.0.10` → `5.0.10`; `>= 3.0.0, < 3.0.7` → `3.0.7`; `>= 2.0.0, < 2.1.5` → `2.1.5`; `< 1.1.19` → `1.1.19` |
| `builder-util-runtime` | high | [GHSA-p2f4-r6v6-j797](https://github.com/advisories/GHSA-p2f4-r6v6-j797) | `<9.7.0` | `< 9.7.0` → `9.7.0` |
| `electron` | high | [GHSA-532v-xpq5-8h95](https://github.com/advisories/GHSA-532v-xpq5-8h95) | `<39.8.1` | `< 39.8.1` → `39.8.1`; `>= 40.0.0-alpha.1, < 40.7.0` → `40.7.0`; `>= 41.0.0-alpha.1, < 41.0.0` → `41.0.0` |
| `electron` | high | [GHSA-8337-3p73-46f4](https://github.com/advisories/GHSA-8337-3p73-46f4) | `<38.8.6` | `< 38.8.6` → `38.8.6`; `>= 39.0.0-alpha.1, < 39.8.0` → `39.8.0`; `>= 40.0.0-alpha.1, < 40.7.0` → `40.7.0`; `>= 41.0.0-alpha.1, < 41.0.0-beta.8` → `41.0.0-beta.8` |
| `electron` | high | [GHSA-jjp3-mq3x-295m](https://github.com/advisories/GHSA-jjp3-mq3x-295m) | `<38.8.6` | `< 38.8.6` → `38.8.6`; `>= 39.0.0-alpha.1, < 39.8.1` → `39.8.1`; `>= 40.0.0-alpha.1, < 40.8.0` → `40.8.0`; `>= 41.0.0-alpha.1, < 41.0.0-beta.8` → `41.0.0-beta.8` |
| `electron` | high | [GHSA-9wfr-w7mm-pc7f](https://github.com/advisories/GHSA-9wfr-w7mm-pc7f) | `<38.8.6` | `< 38.8.6` → `38.8.6`; `>= 39.0.0-alpha.1, < 39.8.0` → `39.8.0`; `>= 40.0.0-alpha.1, < 40.7.0` → `40.7.0`; `>= 41.0.0-alpha.1, < 41.0.0-beta.8` → `41.0.0-beta.8` |
| `electron` | high | [GHSA-v3j7-r9gq-3gjw](https://github.com/advisories/GHSA-v3j7-r9gq-3gjw) | `<39.8.10` | `>= 42.0.0-alpha.1, < 42.0.0` → `42.0.0`; `>= 41.0.0-alpha.1, < 41.4.0` → `41.4.0`; `>= 40.0.0-alpha.1, < 40.9.3` → `40.9.3`; `< 39.8.10` → `39.8.10` |
| `electron` | high | [GHSA-h7rp-cf8h-j98x](https://github.com/advisories/GHSA-h7rp-cf8h-j98x) | `<39.8.9` | `< 39.8.9` → `39.8.9`; `>= 40.0.0-alpha.1, < 40.9.2` → `40.9.2`; `>= 41.0.0-alpha.1, < 41.2.2` → `41.2.2`; `>= 42.0.0-alpha.1, < 42.0.0-beta.5` → `42.0.0-beta.5` |
| `electron` | high | [GHSA-9f4c-93c8-jc8g](https://github.com/advisories/GHSA-9f4c-93c8-jc8g) | `<39.8.10` | `>= 42.0.0-alpha.1, < 42.0.1` → `42.0.1`; `>= 40.0.0-alpha.1, < 41.10.3` → `41.10.3`; `< 39.8.10` → `39.8.10` |
| `electron` | high | [GHSA-hq2x-r82h-9wj4](https://github.com/advisories/GHSA-hq2x-r82h-9wj4) | `<41.10.4` | `< 41.10.4` → `41.10.4`; `>= 42.0.0-alpha.1, < 42.5.2` → `42.5.2`; `>= 43.0.0-alpha.1, < 43.0.0` → `43.0.0` |
| `electron` | high | [GHSA-gr2m-v5gq-v685](https://github.com/advisories/GHSA-gr2m-v5gq-v685) | `<41.10.6` | `< 41.10.6` → `41.10.6`; `>= 42.0.0-alpha.1, < 42.9.2` → `42.9.2`; `>= 43.0.0-alpha.1, < 43.4.1` → `43.4.1`; `>= 44.0.0-alpha.1, < 44.0.0-beta.5` → `44.0.0-beta.5` |
| `electron` | high | [GHSA-j84w-jfhq-vhvj](https://github.com/advisories/GHSA-j84w-jfhq-vhvj) | `<41.10.6` | `< 41.10.6` → `41.10.6`; `>= 42.0.0-alpha.1, < 42.9.2` → `42.9.2`; `>= 43.0.0-alpha.1, < 43.4.1` → `43.4.1`; `>= 44.0.0-alpha.1, < 44.0.0-beta.5` → `44.0.0-beta.5` |
| `electron` | high | [GHSA-9qh4-3jw8-366w](https://github.com/advisories/GHSA-9qh4-3jw8-366w) | `<41.10.6` | `< 41.10.6` → `41.10.6`; `>= 42.0.0-alpha.1, < 42.9.2` → `42.9.2`; `>= 43.0.0-alpha.1, < 43.4.1` → `43.4.1`; `>= 44.0.0-alpha.1, < 44.0.0-beta.5` → `44.0.0-beta.5` |
| `electron` | high | [GHSA-jr5w-w6x2-84p9](https://github.com/advisories/GHSA-jr5w-w6x2-84p9) | `<42.11.16` | `>= 45.0.0-alpha.1, < 45.0.0-beta.6` → `45.0.0-beta.6`; `>= 44.0.0-alpha.1, < 44.9.1` → `44.9.1`; `>= 43.0.0-alpha.1, < 43.8.1` → `43.8.1`; `< 42.11.16` → `42.11.16` |
| `extract-zip` | high | [GHSA-jmr9-qjv8-65gv](https://github.com/advisories/GHSA-jmr9-qjv8-65gv) | `<=2.0.1` | `<= 2.0.1` → `—` |
| `extract-zip` | high | [GHSA-7pqw-9j4j-h8q3](https://github.com/advisories/GHSA-7pqw-9j4j-h8q3) | `<=2.0.1` | `<= 2.0.1` → `—` |
| `http-cache-semantics` | high | [GHSA-ch52-4w7c-c8xp](https://github.com/advisories/GHSA-ch52-4w7c-c8xp) | `<=4.2.0` | `<= 4.2.0` → `—` |
| `ip-address` | high | [GHSA-mwp4-54f8-5fhr](https://github.com/advisories/GHSA-mwp4-54f8-5fhr) | `<=10.3.0` | `<= 10.3.0` → `10.3.1` |
| `js-yaml` | high | [GHSA-5p4m-2wfm-xmqj](https://github.com/advisories/GHSA-5p4m-2wfm-xmqj) | `>=4.0.0 <4.3.1` | `>= 4.0.0, < 4.3.1` → `4.3.1`; `>= 3.0.0, < 3.15.1` → `3.15.1` |
| `js-yaml` | high | [GHSA-2883-xcg3-v3hh](https://github.com/advisories/GHSA-2883-xcg3-v3hh) | `>=4.0.0 <4.3.2` | `>= 4.0.0, < 4.3.2` → `4.3.2`; `>= 3.0.0, < 3.15.2` → `3.15.2` |
| `tar` | high | [GHSA-34x7-hfp2-rc4v](https://github.com/advisories/GHSA-34x7-hfp2-rc4v) | `<7.5.7` | `< 7.5.7` → `7.5.7` |
| `tar` | high | [GHSA-8qq5-rm4j-mr97](https://github.com/advisories/GHSA-8qq5-rm4j-mr97) | `<=7.5.2` | `<= 7.5.2` → `7.5.3` |
| `tar` | high | [GHSA-83g3-92jg-28cx](https://github.com/advisories/GHSA-83g3-92jg-28cx) | `<7.5.8` | `< 7.5.8` → `7.5.8` |
| `tar` | high | [GHSA-qffp-2rhf-9h96](https://github.com/advisories/GHSA-qffp-2rhf-9h96) | `<=7.5.9` | `<= 7.5.9` → `7.5.10` |
| `tar` | high | [GHSA-9ppj-qmqm-q256](https://github.com/advisories/GHSA-9ppj-qmqm-q256) | `<=7.5.10` | `<= 7.5.10` → `7.5.11` |
| `tar` | high | [GHSA-r6q2-hw4h-h46w](https://github.com/advisories/GHSA-r6q2-hw4h-h46w) | `<=7.5.3` | `<= 7.5.3` → `7.5.4` |
| `tar` | critical | [GHSA-23hp-3jrh-7fpw](https://github.com/advisories/GHSA-23hp-3jrh-7fpw) | `<=7.5.18` | `<= 7.5.18` → `7.5.19` |
| `tar` | high | [GHSA-8x88-c5mf-7j5w](https://github.com/advisories/GHSA-8x88-c5mf-7j5w) | `<=7.5.17` | `<= 7.5.17` → `7.5.18` |
| `tar` | high | [GHSA-r292-9mhp-454m](https://github.com/advisories/GHSA-r292-9mhp-454m) | `<=7.5.20` | `<= 7.5.20` → `7.5.21` |

## Verification

After the targeted parent upgrades and fresh lockfile resolution, the same full public-registry npm audit reports **0 vulnerabilities**, including build/development dependencies. Fixed transitive dependencies include patched XML/YAML parsers, archive extraction, cache semantics, address parsing and brace expansion; the old `extract-zip` path is replaced with Electron’s maintained internal extractor. The audit is time-specific, not a guarantee against undisclosed flaws.

Rendered and packaged startup commands/results are recorded in the PR. Tests use temporary application data, an explicit isolated Python environment, and developer-only offline fixtures. No real account/session token, live mirror scan, VPN operation or production history is involved.


## Rendered and packaged verification

The developer harness launches the actual Electron application and the built macOS executable from a temporary directory, with a restricted PATH and no activated venv. It uses explicit absolute interpreter preferences, temporary per-app configuration/history, and a developer-only Python fixture that replaces scanning while executing the real bridge/serializers/history. Fixtures are excluded from the packaged app.

Scenarios cover missing Python, clean Python without required packages, real Python and packaged config load, settings preservation (90-second timeout), rejected arbitrary config paths over IPC, progress/results for the entire canonical inventory, blocked/rate-limited/DNS states, zero/missing timing order, cancellation/restart, history, failed-scan dashboard reset, unsafe window URLs, child shutdown and macOS close/reactivate. An expected CSP rejection of a JavaScript URL is asserted explicitly; unexpected page errors fail the check. Screenshots/failure diagnostics stay in temporary directories. GUI export controls do not exist; Python JSON/CSV export is covered by the Python suite.

Python is not bundled. The GUI verifies Python >=3.12, required module imports and the declared dependency minimums. Use `python-path.txt` in the app's data directory or `STAKE_PYTHON` for an absolute executable path; neither is accepted through renderer IPC. Missing/incompatible environments leave Run disabled and display setup guidance. On macOS, standard Homebrew paths are tried only if no explicit interpreter is configured. Probe and bridge processes use isolated Python mode.

All desktop builds are unsigned/unnotarized. No release, tag, public release asset or package publication is part of this work.


Local completion gates: 115 Python tests, 8 Node tests, 11 rendered development scenarios and 11 packaged macOS scenarios pass. Ruff lint/format, import checks, mypy, Bandit, locked Python audit, Python wheel/sdist builds and unsigned macOS app/DMG/ZIP builds pass. The packaged process reports Electron 43.8.3, loads the canonical inventory and Python bridge from Resources, and excludes Playwright/fixtures from ASAR. Full optional/development npm graph audit reports zero findings. Fresh GitHub runs are linked in PR #94 and must pass at the final head before merge.
