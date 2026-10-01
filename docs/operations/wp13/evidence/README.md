# WP13 validation evidence

Read `../DEPLOYMENT.md`, `../MODEL_BUNDLE.md`, `../RECOVERY.md` and
`../REVIEW.md` alongside these reports. Tests use disposable synthetic data;
no production deployment, public exposure or homelab modification occurred in
the review/fix task. DevOps owns platform changes and activation evidence.

## Corrected current candidate

`release.json` contains actual GHCR multi-platform version@digest pins for
[prerelease v0.1.0-wp13.7](https://github.com/Pieter-OHearn/grid-oracle/releases/tag/v0.1.0-wp13.7),
source `1942bb859a13e532c7ade24de203a38186705500`, rebased onto main
`897ff95772c822f3fac5c08d38357c0a9dd51f36` (WP12 PR #107 integration).
[Release run 36906440683](https://github.com/Pieter-OHearn/grid-oracle/actions/runs/36906440683)
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

Local rebased validation: Python 3.12.14, locked uv 0.12.19, 518 backend tests
passed with one existing optional skip, including twelve targeted ops tests and nineteen release tests;
Bun 1.4.2, twenty dashboard tests, typecheck/lint/build; Ruff/format/whitespace
passed. The twelve ops tests include v1 compatibility, actual live-mount
corruption, null pre-ledger comparison, missing-ledger preflight, legacy
EVALUATE blocking and a 24 MiB lineage memory regression with peak Python
allocation below 8 MiB. Full native release checks repeat these suites.

Released-digest observations (100 GETs, one client, synthetic fixture):

| Native host | GET p95 | Restore including negative live-mount check | Worker peak RSS |
| --- | --- | --- | --- |
| amd64 | 43.53 ms | 22.07 s | 220.58 MiB |
| arm64 | 41.86 ms | 20.16 s | 210.56 MiB |

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

## Release-pipeline presentation and tag evidence

The owner requested pipeline-created tags, changelog notes and package descriptions.
The manual entry point takes a shared SemVer version on main, fixes its source SHA,
tests it and creates an annotated tag before publication. The same helper created
staging tag `.7`; disposable bare-remote tests verify exact source/refusal behavior.
GitHub manual dispatch itself becomes available after default-branch integration;
it was not invoked on an unmerged feature branch and no merge was performed.

`release-notes.md` is the actual published `.7` body: image links/descriptions,
three digest pins, commit changelog and `.4`→`.7` comparison. GitHub merged-PR
notes are preserved; unmerged staging ranges get a commit-list fallback.
Default baseline is the last actually published release, excluding failed tags
and drafts. `image-metadata.json` contains the three actual raw OCI indexes'
descriptions, versions, source revisions and native platforms. Native publication
also checked that all six OCI config IDs equal their tested Docker candidates.
Actionlint (including shellcheck), Ruff/format/whitespace, full backend/dashboard
checks and both candidate/released recovery matrices passed on `.7` source.

Previous `.4` receipt/reports are retained in `v0.1.0-wp13.4/`. It already fixes
the five recovery findings, but has no image descriptions or release changelog.
Failed `.5` (run 36904435107) built/tested both architectures but Docker-format
manifest lists dropped index annotations; the metadata gate stopped publication
of a GitHub release. `failed-v5-api-index.json` preserves its raw diagnostic.
`.6` (run 36905334727) was cancelled after discovering the same known export issue.
Neither tag was reused or counted as a successful release. `.7` uses OCI registry
export from the verified build cache and checks annotations from raw manifests.
A tiny local scratch-image probe independently confirmed config-hash equality;
only its two owned image references were removed afterward.
