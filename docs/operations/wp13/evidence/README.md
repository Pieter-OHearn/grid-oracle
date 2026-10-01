# WP13 validation evidence

Read `../DEPLOYMENT.md`, `../MODEL_BUNDLE.md` and `../RECOVERY.md` with these
machine-readable reports. All local tests use disposable synthetic data and
owned temporary resources. No production database, infrastructure change or
public exposure occurred.

- `capacity.json`: read-only SSH host/RAM/load/storage measurement, with UTC
  capture time and raw output; primary ARM Pi vs AMD64 Proxmox and separate HDD.
- `base-images.json`: public registry index digests and native architectures.
- `local-candidate.json`: pre-release local ARM64 install/upgrade, stale-backup
  rejection, repeat upgrade, bounded ledger work, restart with no training host
  or provider, network boundaries, memory/latency and new-environment restore.
  This report is explicitly candidate validation, not a GHCR release receipt.

Local environment: macOS ARM64, Docker Linux VM ~7.75 GiB, Python 3.12.14,
uv 0.12.19, Bun 1.4.2. Full native release validation passed 484 backend tests with one existing
optional backend skip; the suite includes six targeted recovery/bundle tests.
Dashboard: 16 tests, ESLint/typecheck/build pass. Ruff/format/whitespace pass.
The release workflow repeats the full checks and native image drill on AMD64
and ARM64 before publishing. Release `v0.1.0-wp13.3` succeeded in
[run 36866480857](https://github.com/Pieter-OHearn/grid-oracle/actions/runs/36866480857).

Observed failures were fixed, not converted into successes: normal Docker
client credential/metadata context timed out; an isolated client config with
the same runtime succeeded. YAML flow-list tmpfs options needed quotes. The
synthetic fixture writer needed its own writable override, while serving stays
read-only. An internal-only Docker network does not provide a reliable host
port path on this runtime; only frontend attaches to the edge network, with
loopback staging publication. API/DB remain private. The bounded ledger probe
uses a declared simulated time, not wall-clock provider work.

The measured HDD backup path, production secret/role creation, real bundle,
representative loaded-host measurements, app/DB trace spans and public ingress
are production release prerequisites; they are never represented by synthetic
or same-disk local test evidence.

Native CI first built both architectures successfully, then exposed host UID
copy/cleanup failures for application-owned 0600 artifacts on Linux. The drill
now copies with the same non-root UID in a network-disabled tools container and
only relaxes synthetic temporary directories for owned cleanup. Failed runs
36864322438 / prerelease v0.1.0-wp13.1 are retained as superseded diagnostics;
no failed version is reused or represented as a released image.

The second Linux copy attempt found metadata ownership on an existing host-owned
destination. The final copy creates its own target directory under the permitted
fixture parent, so files and directories have the application UID throughout.
CodeQL also flagged generated fixture passwords written to temporary files.
The synthetic-only DB now uses trust authentication on the internal unpublished
network; no fixture password exists. Production SOPS/password-file separation
in the homelab proposal remains required. No alert was dismissed or suppressed.

- `release.json`: actual GHCR multi-platform index pins for prerelease
  `v0.1.0-wp13.3`, source `d22b650d221c256ef41a077d1eef1d52a8323b7e`,
  [published receipt](https://github.com/Pieter-OHearn/grid-oracle/releases/tag/v0.1.0-wp13.3).
- `native-amd64.json` / `native-arm64.json`: successful nine-check native
  candidate reports from that release run. Both include full lineage/output
  and bundle hashes, saved-forecast restart, network checks and measurements.
- `local-released-disk-full.json`: failed released-digest attempt retained as
  diagnostic evidence. Registry pulls worked, but the shared local Docker VM
  reached 100% of its 59 GiB disk and PostgreSQL could not write its init file.
  No unrelated images/build caches were pruned. Fresh native CI runners perform
  released-digest acceptance; this failed report is never counted as passed.

The final workflow-only follow-up verifies pulled released digests on fresh
native runners and does not change the source packaged in the `.3` images.
It uses the committed release receipt on PRs and the just-published receipt on
future tag runs, with read-only registry permission for this verification job.

- `released-amd64.json` / `released-arm64.json`: **passed** fresh-runner
  installation/recovery from the actual `.3` version@digest indexes in
  [run 36867960802](https://github.com/Pieter-OHearn/grid-oracle/actions/runs/36867960802)
  on validation source `e79360df8ac98094072a261429b5ab43519d55d5`.
  Each passed all nine checks and restored all ten lineage tables, 88 forecast
  output hashes, two publication records and the pinned model bundle. Training
  machines/providers were absent; exact saved forecast responses survived
  restart and a new-environment restore.

Released-digest observations (100 GETs, one client, synthetic fixtures):

| Native host | GET p95 | Restore | Worker peak RSS |
| --- | --- | --- | --- |
| amd64 | 31.84 ms | 18.1 s | 223.2 MiB |
| arm64 | 38.68 ms | 17.04 s | 210.54 MiB |

These are fresh GitHub runner measurements, not loaded homelab or real-data
inference SLOs. Each report records the exact three image pins, schema revision,
receipt/bundle hashes, per-table hashes and memory caps/usage. Backfill remains
one worker/event; the measured workload is a 24-revision synthetic ledger
probe, with no provider requests or production prediction throughput claim.
Only the two released image references actually downloaded by the failed local
drill were removed afterward; its frontend was never pulled. Existing images,
volumes and shared build caches were preserved.
