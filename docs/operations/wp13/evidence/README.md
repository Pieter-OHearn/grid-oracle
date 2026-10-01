# WP13 validation evidence

Read `../DEPLOYMENT.md`, `../MODEL_BUNDLE.md`, `../RECOVERY.md` and
`../REVIEW.md` alongside these reports. Tests use disposable synthetic data;
no production deployment, public exposure or homelab modification occurred in
the review/fix task. DevOps owns platform changes and activation evidence.

## Corrected current candidate

`release.json` contains actual GHCR multi-platform version@digest pins for
[prerelease v0.1.0-wp13.4](https://github.com/Pieter-OHearn/grid-oracle/releases/tag/v0.1.0-wp13.4),
source `9e726efa1ffac737bc35c645e6d52841a0205a3a`, rebased onto main
`897ff95772c822f3fac5c08d38357c0a9dd51f36` (WP12 PR #107 integration).
[Release run 36884062642](https://github.com/Pieter-OHearn/grid-oracle/actions/runs/36884062642)
passed all tests, both native builds/drills, immutable release assembly and
both fresh-runner pulls/restore drills. `native-{amd64,arm64}.json` records
candidate validation; `released-{amd64,arm64}.json` records actual GHCR pulls.

Each report passes twelve checks: initial empty/pre-ledger comparison; backup
before bootstrap/schema upgrade to `20260929_05`; stale-schema rejection;
removed-ledger rejection before DDL; fresh repeated upgrade; native scientific
libraries/bounded ledger backfill; non-root read-only serving; private metrics;
offline saved-forecast restart; unpublished DB/API and loopback frontend;
corrupt live artifact rejection with intact backup; new-volume restore with
all ten lineage table hashes, 88 forecast output hashes, model-bundle closure
and identical saved public responses. Replacement runtime mounts are distinct
from the recovery-set mounts. New receipts use streaming recovery format v2.

Local rebased validation: Python 3.12.14, locked uv 0.12.19, 499 backend tests
passed with one existing optional skip, including twelve targeted ops tests;
Bun 1.4.2, twenty dashboard tests, typecheck/lint/build; Ruff/format/whitespace
passed. The twelve ops tests include v1 compatibility, actual live-mount
corruption, null pre-ledger comparison, missing-ledger preflight, legacy
EVALUATE blocking and a 24 MiB lineage memory regression with peak Python
allocation below 8 MiB. Full native release checks repeat these suites.

Released-digest observations (100 GETs, one client, synthetic fixture):

| Native host | GET p95 | Restore including negative live-mount check | Worker peak RSS |
| --- | --- | --- | --- |
| amd64 | 43.49 ms | 22.17 s | 222.34 MiB |
| arm64 | 41.61 ms | 21.12 s | 210.61 MiB |

Serving memory samples are about 70 MiB API/256 MiB cap, 51 MiB DB/512 MiB cap
and 3 MiB frontend/64 MiB cap. Worker cap is 768 MiB; tools cap is 256 MiB.
These are fresh GitHub runner measurements, not loaded homelab or real-data
inference SLOs. Backfill is one worker/event with 24 synthetic ledger revisions,
zero provider requests and no production prediction throughput claim.

## Discovery and retained history

- `capacity.json`: authorized read-only SSH host/RAM/load/storage measurement;
  primary ARM Pi NVMe and proposed separate AMD64-host HDD.
- `base-images.json`: pinned public registry indexes and native platforms.
- `local-candidate.json`: earlier local ARM64 nine-check candidate validation,
  not current corrected-image or GHCR acceptance.
- `v0.1.0-wp13.3/`: original receipt and four successful nine-check reports,
  source `d22b650d221c256ef41a077d1eef1d52a8323b7e`. Runs 36866480857 and
  36867960802 passed the prior checks. This image predates the five findings
  and must not be promoted as the corrected candidate.
- `local-released-disk-full.json`: earlier failed `.3` pull/drill. Registry
  access worked but the shared 59 GiB Docker VM filled during PG init. Only
  two own downloaded image references were removed; unrelated images, volumes
  and shared caches were preserved. Fresh native CI avoids that disk limit.

Failures remain failures: original Docker credential/metadata timeout was
resolved with an isolated client config. Tmpfs quoting, fixture-only writer
mounts, Linux UID copy/cleanup and simulated ledger time were corrected.
Failed `.1`/`.2` tags (runs 36864322438/36865467747) were never reused and
published no release. CodeQL password-fixture alerts were repaired with trust
only on the unpublished synthetic DB; production secret separation is required.

During review validation, PR run 36884060650 built the corrected candidates
successfully but still read the old `.3` receipt. Its released jobs failed on
the newly added empty/pre-ledger comparison with a missing provenance table,
confirming the historical defect. It is superseded by the successful `.4`
release run and the subsequent PR run using the committed `.4` receipt.

The real model bundle, provenance-aware prediction/publication/evaluation
adapters, physical off-primary transfer/provisioning, representative loaded-host
measurements, application/DB trace spans and public-ingress policy remain
activation dependencies. Synthetic or same-disk evidence does not satisfy
those production gates. Large v1 recovery inventories retain their original
algorithm and need adequate memory or their original pinned tools image;
new v2 receipts avoid whole-table materialization.
