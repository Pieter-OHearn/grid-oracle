# Recovery, migration and rollback runbook

Restore owner: Pieter O'Hearn / homelab platform owner; a delegate needs owner
assignment. Application code/CI lives in GridOracle, runtime and SOPS in
homelab. RPO target <=24 h plus a new verified set after model promotion and
publication; RTO target <=60 min for a prepared replacement. These are budgets,
not homelab measurements or promises of whole-site recovery.

## Coordinated backup

1. Stop scheduler/worker and any operator publication/backfill writers. Keep
   public reads running; prohibit another writer until verification completes.
   Record database name, schema revision, release pins and selected bundle hash.
2. On the DB service, use the matching PostgreSQL 16 client to write
   `pg_dump -U gridoracle_admin -Fc --no-owner --no-acl DATABASE` to a **new**
   backup directory's `database.dump`. Do not copy live PGDATA files.
3. Run the same released API tools image with its admin URL-file secret and
   artifact/bundle read mounts:
   `python -m scripts.wp13_recovery seal --directory /recovery`.
   This copies the whole content-addressed artifact tree and bundle, verifies
   every persisted forecast output/artifact hash, and writes `recovery.json`.
   Capture its printed SHA256 outside the set in the protected backup catalog.
   A sealed directory cannot be reused. Empty initial installations still need
   a dump and selected bundle closure, with null pre-ledger schema/lineage.
4. Transfer the complete set to the approved off-primary physical HDD using
   the restricted backup principal. Transfer to a temporary directory and
   rename after verification. Verify `recovery.json` against its external hash
   and all declared files **on the destination**. No successful-transfer claim
   may be inferred from a same-disk local copy.
5. Restore the set into a new isolated database/environment, compare hashes as
   below, and record verification. Only then record backup success/age, retain
   according to seven daily/four weekly/three monthly policy, and restart
   writers. Delete sets only through the backup owner; keep the last verified
   set and every retained forecast's referenced artifact. Monitor quota/free
   capacity before retention rotation, not after it.

Secrets/age recovery and restricted SSH credentials are provisioned by the
owner. Keep an offline age-key recovery copy outside the primary disk; never
place a key in reports. The measured HDD is a separate disk/host from the Pi,
but no new backup directory, SSH principal or automated rotation has yet been
provisioned. Until that path passes an actual transfer/restore, it is a release
blocker. Logs/traces are not part of the recovery source of truth.

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
schema unchanged since backup and immutable lineage unchanged since backup,
then upgrades using the integrated inspector/Alembic ledger. A fresh **empty**
database additionally requires explicit `--bootstrap-empty`, initializing only
the historical SQL baseline before ledger upgrades; never attach initialization
SQL or sample fixture mounts to production PostgreSQL. `--bootstrap-empty`
refuses to reinitialize nonempty targets and the normal inspector refuses
unrecognized schemas. Upgrade is not API startup behavior.

For a repeat upgrade after schema changed, take a new backup: the old receipt
is rejected. Review the migration SQL/expected locks and time budget before a
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
   never use `--clean` on the old production database. Recreate reader/worker
   roles/grants from reviewed homelab configuration and owner-held SOPS values.
3. Mount the backed-up artifact tree and backed-up bundle in the replacement,
   read-only, with its exact SHA256. Set replacement URL files from SOPS.
   Run `scripts.wp13_recovery compare --directory /recovery
   --receipt-sha256 RECEIPT` against the replacement. This verifies DB lineage
   table counts/hashes, each forecast output hash, every stored artifact hash,
   selected bundle closure and schema revision. Require the selected bundle's
   DB bindings before readiness.
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
