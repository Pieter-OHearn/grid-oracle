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
uv 0.12.19, Bun 1.4.2. Backend baseline passed 482 tests with one existing
optional backend skip; six targeted recovery/bundle tests subsequently passed.
Dashboard: 16 tests, ESLint/typecheck/build pass. Ruff/format/whitespace pass.
The release workflow repeats the full checks and native image drill on AMD64
and ARM64 before publishing; GHCR release/digest reports are added after that
workflow succeeds.

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
