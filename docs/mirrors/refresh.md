# Mirror inventory and refresh

`config.yaml` is the offline source of truth for CLI and GUI scans. Neither
application scrapes at startup. The directory at https://playstake.fans/ loads
https://mirrorslist.playstake.io/mirror-list.json. Its JSON contains HTTPS
origins, not server health assertions. The frontend removes `stake.com` from its
cards and performs visitor-side, no-CORS HEAD checks against `/_api/graphql`.
That browser's "online" count varies by network and is not an authenticity test.

The initial refresh retrieved 118 unique destinations at
2026-10-24T13:32:17.015330+00:00: the primary domain and 117 alternatives.
Thirteen matched the former 16-entry configuration; 105 were added. The absent
`stake1001.com`, `stake1002.com`, and `stake1003.com` were retained by explicit
owner approval. The configured union is 121. These are snapshot observations,
not expected counts for future updates. See `source-snapshot.yaml` for the full
source list and added/retained/removed diff.

## Refresh workflow

From a clean task branch at the repository root:

```sh
uv sync --locked
uv run --frozen python -m src.mirror_update
uv run --frozen python -m src.mirror_update --apply
uv run --frozen pytest tests/ -v
git diff -- config.yaml docs/mirrors/source-snapshot.yaml
```

Preview is the default. `--config` and `--snapshot` select explicit paths. The
updater uses a 15-second total timeout, a bounded JSON response, HTTPS-only
origins, normalized IDNs/hostnames, and deduplication. It preserves existing
entries, custom fields, settings, trust configuration, and comments. Newly
listed domains are appended in deterministic order; nothing is removed or
marked trusted. All previously listed domains must still be present before
`--apply` will write, even for a same-size substitution. Empty, failed, malformed,
or reduced results leave both files untouched. Review source changes manually
when this guard triggers; do not guess missing domains or bypass access controls.

Each file is replaced atomically. Snapshot replacement precedes config
replacement. A crash between those operations can leave a newer snapshot beside
the old, still valid configuration. `config_sha256` identifies the intended
configuration; the next preview reports `config_changed_since_snapshot` when
it differs. Legitimate manual config/settings edits also cause that warning.
Inspect/retry the preview after interruption. The two files are
not a transactional database. Source listing does not guarantee a complete
upstream inventory, ownership, authenticity, or current reachability.

## Destination and result semantics

Configuration requires matching `domain` and URL hostnames, with no userinfo,
paths (except a root slash), query, or fragment. Hostnames use lowercase ASCII
IDNA; custom unauthenticated entries may use HTTP/HTTPS and valid explicit ports.
Discovered entries require standard HTTPS. Numeric/non-numeric destinations and
all DNS answers used for requests must be public; localhost, private, link-local,
multicast and metadata destinations are rejected. Redirects are not followed.
Environment proxies are not used for mirror probes. Private-network custom
scans formerly accepted by this tool are no longer supported.

A scan reports local observations: `http_responding`, `blocked_or_challenged`,
`rate_limited`, `redirect_unverified`, HTTP/TLS/request failure, DNS failure/timeout,
or destination rejection. A 403/429/timeout never proves the site is offline.
A successful HEAD, even HTTP 200, leaves `application_status: unverified`; challenge
pages can also return 200. No authenticity or application-content claim is made.

Ranking uses only successful HTTP HEAD response latency, over the configured
rounds, with failed/blocked/missing results last. HTTPS is the default inventory
scheme. Do not compare a custom HTTP entry with HTTPS entries as equivalent TLS
work. TCP and authenticated API timings remain separate measurements. The legacy
`best_ms` field now carries this ranking metric; `is_up` means an eligible HTTP
response, not verified application health. SQLite additions preserve old rows,
marked `legacy`; old `best_ms` values used a different metric. Historical "uptime"
is a legacy/local HTTP response statistic, not service availability.

Rounds must be 1–20, timeout greater than zero and at most 120 seconds, and
concurrency 1–64. The configured limit applies to CLI and GUI. DNS waits and
requests are bounded, but operating-system DNS worker calls cannot be forcibly
terminated by Python. Cancellation cancels pending scan work; GUI termination
owns its child until exit and escalates after three seconds.

Authenticated API tests remain opt-in, with an empty trusted-host list by
default. Discovery never expands it. Tokens require matching HTTPS hosts,
validated/pinned public DNS and no redirects. Maintenance verification uses no
account, token, API query or betting operation.
