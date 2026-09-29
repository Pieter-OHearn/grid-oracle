# Immutable forecast lineage contract

WP03 introduces an additive, append-only storage contract. It does not change
the legacy `predictions` read path; WP11 is responsible for switching public
reads after it consumes these records.

## Artifact manifests

Every artifact is written through `ContentAddressedArtifactStore` at a logical,
portable path of this form:

```text
<namespace>/sha256/<lowercase-sha256>
models/<model-id>/sha256/<lowercase-sha256>
```

The database stores the logical path and SHA-256 separately. Both must verify
before a raw snapshot, dataset, feature snapshot, model or calibrator manifest
is inserted. A model manifest additionally requires its path to match its
declared model ID exactly and a non-null legacy `model_version_id`. Files are
first fsynced at an unpublished same-directory temporary path, then atomically
linked into their content-addressed path. Absolute paths, traversal and
incorrect hashes fail.

Example model manifest:

```json
{
  "model_manifest_id": "model-2026.1-a1",
  "model_id": "champion-v1",
  "artifact_path": "models/champion-v1/sha256/4d5c...",
  "sha256": "4d5c...",
  "manifest": {"format": "xgboost-json", "seed": 7}
}
```

## Forecast lifecycle

`ForecastRunInput` requires the horizon, input cutoff, actual issue time,
source-availability time, provenance grade, expected field size, explicit
idempotency key and deterministic input manifest. Verified/observed runs also
require raw snapshot, dataset, feature snapshot, model and calibrator
references. `legacy_unverified` is the only grade permitted to retain unknown
legacy timing/lineage.

The run ID is a SHA-256 fingerprint of this immutable input. Retry with the
same idempotency key and fingerprint returns the original run; a different
payload fails. This comparison normalizes PostgreSQL-decoded JSON and timestamp
values rather than comparing driver return types. Entry output rows are
similarly write-once and content-hashed; no append is allowed after publication
or once the declared field size is reached.

Publication inserts one immutable `forecast_publications` pointer, keyed by
`race_id` and horizon, in the same transaction that checks the exact expected
field count. Thus pre-weekend and post-qualifying pointers coexist, while a
partial field, post-race issue/publish time, result-linked run or conflicting
pointer cannot become a live forecast. `publish` reads the latest persisted
`event_sessions` `race` revision inside its transaction, so callers cannot
supply a stale race start; it also rejects publication before issue time. A
pointer is deliberately not a “latest model” selector.

## Evaluation and result corrections

`result_revisions` remain revisions: a later correction is a new row, not an
update. Every `evaluation_runs` record names both the forecast run and result
revision. Evaluations can therefore be corrected without changing stored
forecast outputs or their publication pointer.

All WP03 lineage, output, evaluation and publication tables have database
triggers that reject updates and deletes on PostgreSQL and SQLite. New records
are the only way to represent new knowledge.

## Reproduction tolerance

Each run declares `reproduction_tolerance` (default `1e-12`) and has a saved
input manifest plus output JSON hashes. `verify_reproduction` runs an isolated
reproducer against that manifest and checks the exact stable entry set and all
numeric values within the recorded absolute tolerance. The predictor's
dependency/model versions belong in the model manifest; callers must retain
the referenced artifact directory during backup and restore.

## Migration, legacy import and rollback

Alembic revision `20260929_04` is additive. It leaves the old tables and reads
available. `import_legacy_forecast` preserves legacy prediction values, known
creation timestamps and model-version ID as `legacy_unverified`; unknown
cutoff, availability and artifact lineage are explicitly recorded as unknown,
never inferred. `import_legacy_predictions` is the explicit, non-automatic
operator action that groups existing `predictions` rows by their known race,
model and creation time before calling that importer. It is never invoked by
Alembic or application startup. Legacy records cannot be published as live
forecasts. Their horizon is stored as `unknown`, not guessed as pre-weekend or
post-qualifying. Importing a field and its output rows is one transaction, and
legacy `NUMERIC` confidence values are retained as their exact decimal text.

Do not downgrade a database containing WP03 history as a normal rollback: the
Alembic downgrade removes the additive tables and therefore requires a verified
pre-upgrade backup/restore. Operational rollback is to stop writing/reading the
new contract while retaining its immutable records. No deployment or live-data
backfill is part of this migration.
