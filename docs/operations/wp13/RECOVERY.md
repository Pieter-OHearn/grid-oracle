# Recovery, migration and rollback runbook

Restore owner: Pieter O'Hearn / homelab platform owner; a delegate needs owner
assignment. Application code/CI lives in GridOracle, runtime and SOPS in
homelab. RPO target <=24 h plus a new verified set after model promotion and
publication; RTO target <=60 min for a prepared replacement. These are budgets,
not homelab measurements or promises of whole-site recovery.

## Coordinated backup

The backup sidecar runs `python -m gridoracle.ops.backup loop --root /backups`
(worker image, administrator URL, artifacts and bundle read-only). Each night,
and at once whenever no verified set is under 26 hours old, it:

1. Takes the maintenance advisory lock exclusively. Every scheduler and worker
   tick holds it shared, so running ticks finish and no new tick starts until
   the set is sealed; public reads keep running.
2. Writes `pg_dump --format=custom --no-owner --no-acl` (PostgreSQL 16 client,
   password from the environment) to a new staging directory's
   `database.dump`. Live PGDATA files are never copied.
3. Seals the set (`scripts.wp13_recovery.seal`): copies the whole
   content-addressed artifact tree and the selected bundle, verifies every
   persisted forecast output and artifact hash, and writes `recovery.json`.
   Then it releases the lock.
4. Verifies the staged set against its receipt from disk, moves it into
   `sets/<UTC time>` (one rename), and only then writes the receipt hash to
   `receipts/<UTC time>.sha256`. A set name is never reused.
5. Keeps the newest two sets, verifies every retained set again, and writes
   `status/status.json`, which the API's `/metrics` reports as
   `gridoracle_backup_*` gauges. A failed attempt is retried after 30 minutes.

The platform copies the backup directory off the host and keeps the history
(seven daily, four weekly and at least three monthly sets). No
successful-transfer claim may be inferred from the local copy: verify a set on
the destination by restoring it, as below. Delete history only through the
backup owner; keep the last verified set and every retained forecast's
referenced artifact.

Secrets and the platform's backup credentials are provisioned by the owner.
Keep an offline age-key recovery copy outside the primary disk; never place a
key in reports. Until a set restored from the platform's off-host copy passes
the comparison below, it is a release blocker. Logs/traces are not part of the
recovery source of truth.

New receipts use `gridoracle-recovery-v2`: primary-key ordered canonical JSON
row arrays hashed incrementally with 100-row PostgreSQL server-side batches.
All ten immutable tables retain counts/hashes and artifact/output validation.
The reader accepts v1 receipts using their original digest-sorted-row algorithm;
large v1 inventories require adequate memory or their original pinned tools
image. Do not relabel a v1 receipt as v2 or replace its external hash.

## Schema upgrade preflight

Inspect the target with the integrated `scripts.db_migrate` dry-run command,
using the tools container's URL secret rather than printing credentials.
Validate the expected current Alembic revision and image/bundle pins. Reject
unknown schemas or a wrong database. Quiesce all writers and create/verify the
fresh coordinated **off-primary** backup first. Run the proposed homelab
one-shot `migrate` service before API/workers, via compose_stack's existing
`compose.migrations` mechanism. It invokes:

```text
python -m scripts.wp13_migrate --backup /recovery --receipt-sha256 RECEIPT
```

The command verifies receipt/files/bundle, database identity, age <=24 h,
schema unchanged since backup (including a removed revision ledger), actual
runtime artifact tree/selected bundle and immutable lineage unchanged since backup,
then upgrades using the integrated inspector/Alembic ledger. A fresh **empty**
database additionally requires explicit `--bootstrap-empty`, initializing only
the historical SQL baseline before ledger upgrades; never attach initialization
SQL or sample fixture mounts to production PostgreSQL. `--bootstrap-empty`
refuses to reinitialize nonempty targets and the normal inspector refuses
unrecognized schemas. Upgrade is not API startup behavior.

For a repeat upgrade after schema changed, take a new backup: the old receipt
is rejected. Changed artifacts or bundle selection also require a new coordinated
backup. Review the migration SQL/expected locks and time budget before a
schema-changing promotion. The deployer stops on a nonzero migration; do not
allow subsequent up/publication. No automatic destructive downgrade exists.
The existing compose_stack role does **not** quiesce writers; the maintenance
step is an explicit precondition, not a behavior claimed of the deployer.

## Restore into a new environment

1. Select a retained receipt from the external backup catalog, verify its
   SHA256, then run `scripts.wp13_recovery verify`. Any missing/changed/extra
   file or symlink fails. Pull the exact saved version@digest images for the
   new host's native architecture. If registry access is unavailable, use an
   owner-maintained exported image cache with recorded OCI checksums.
2. Create a new project and **empty** PostgreSQL 16 data directory on new
   storage. Restore with `pg_restore --no-owner --no-acl --exit-on-error`;
   never use `--clean` on the old production database. Recreate the reader and
   worker roles with `python -m gridoracle.ops.roles` from the owner-held URL
   secrets.
3. Mount the backed-up artifact tree and backed-up bundle in the replacement,
   read-only, with its exact SHA256. Set replacement URL files from SOPS.
   Run `scripts.wp13_recovery compare --directory /recovery
   --receipt-sha256 RECEIPT` against the replacement. This verifies the **configured live** artifact/bundle mounts against the
   sealed set, then DB lineage table counts/hashes, each forecast output hash, every stored artifact hash,
   selected bundle closure and schema revision. Require the selected bundle's
   DB bindings before readiness. Empty/pre-ledger rollback targets compare null
   schema/lineage without querying missing tables; they need migration before
   application serving, using their selected historical image contract.
4. Start API/frontend with jobs disabled. Verify both seasons/horizons,
   publication-only exposure, exact saved forecast responses and private
   metrics/DB separation. Training machines and external providers remain
   unavailable. Restore ledger leases only after serving passes; reviewed
   scheduler/worker restart recovers expired leases idempotently.
5. Measure duration/memory/GET p95 and review network exposure from allowed
   and denied clients, including IPv6. Route cutover is another authorized
   reviewed homelab PR; preserve the old environment until the owner accepts
   the restore. Never expose the drill environment publicly.

## Serving rollback and migration failure

For a compatible additive schema, revert the homelab **image/bundle promotion**
through a reviewed PR to the last known-good version@digest and bundle hash;
retain immutable DB history. The deployer applies the merged revert and checks
health/exposure normally. Do not resolve a failure by following `latest`,
running training, hand-editing a live stack or changing publication pointers.

For an incompatible schema or partially applied historical bootstrap, stop
writers and retain the failed target for investigation. Restore the verified
pre-upgrade set into a **new** environment with the previous images; compare
its hashes before authorized cutover. Do not Alembic-downgrade/delete WP03
history. Record the loss window against the declared RPO, reconciliation work,
new restore identity and operator acceptance. Retry from a verified target;
never stamp an unknown half-initialized schema merely to silence Alembic.

## Reproduce local acceptance

```text
python scripts/wp13_drill.py --release-json release.json --output drill.json
```

This creates two randomly named local Compose projects, a backed-up initial
schema upgrade, synthetic published forecasts, a restart without research
hosts/providers, and a new-volume restore with exact hashes/response comparison.
It records loopback-only exposure, memory and 100 GET timings, then removes only
its own projects/volumes. `--candidate` is for pre-release CI validation; that
mode is explicitly **not** released-digest acceptance. Neither local mode
proves the physical homelab backup transfer or public ingress.
