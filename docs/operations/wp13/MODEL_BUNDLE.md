# Offline model-bundle contract v1

A bundle is an immutable JSON file externally pinned by SHA256 in the reviewed
homelab configuration. `gridoracle.ops.bundle.verify_bundle` checks the JSON
bytes and every dependency using the WP03 portable content-addressed paths.
Its format is `gridoracle-model-bundle-v1` and these fields are required:

| Field | Meaning |
| --- | --- |
| `model` | `id`, `path`, `sha256`; path must be `models/<id>/sha256/<hash>` |
| `training_data` | Immutable training dataset id + portable path + artifact hash |
| `feature_schema` | Explicit feature-schema id + portable path + schema hash |
| `calibration` | Calibration id + portable path + artifact hash |
| `artifacts` | Nonempty complete runtime artifact closure, each path/hash |
| `model_manifest_id` | Persisted WP03 model manifest |
| `dataset_id` | Persisted training dataset manifest |
| `feature_snapshot_id` | Persisted features, belonging to that dataset |
| `calibrator_manifest_id` | Persisted calibrator, belonging to that model |
| `code_revision` | Code identity used by the bundle producer |
| `runtime_image` | Version-and-digest-pinned worker image for offline execution |

Public-read readiness binds model/data/calibrator hashes and IDs to WP03's
stored manifests. Do not substitute the largest legacy model ID, a machine's
absolute path, an unapproved research winner or a freshly trained artifact.
Include feature schema, preprocessing/encoder/configuration and all necessary
raw/data/feature references in the closure. Copy the **entire** artifact tree
for recovery, not only the selected model: older forecast lineage remains
referenced. A bundle change is another reviewed manifest promotion.

WP09 retained the evaluated baselines and explicitly did not create a
production refit. The production bundle is therefore those fixed fallbacks:
`standings` pre-weekend and `qualifying` post-qualifying, temperature 4.0,
identity calibration (`gridoracle-fixed-baseline-v1`). Nothing is fitted; each
forecast's inputs are the live Jolpica observation frozen in its raw snapshot
and feature snapshot. It makes no claim of a production champion.

- `python -m gridoracle.ops.production_bundle write --bundles DIR
  --runtime-image WORKER_PIN --code-revision SOURCE_SHA` writes the closure
  into the artifact store and `DIR/<sha256>.json`, without a database, and
  prints the SHA256 to pin. The same inputs always give the same bytes.
- `python -m gridoracle.ops.production_bundle register` records the bundle's
  dataset, feature-schema snapshot, model and calibrator manifests (and one
  `model_versions` row) in the migrated database, then checks the selection.
  Serving readiness and evaluation need these rows.

The WP13 drill still uses WP11's synthetic bytes; it proves storage recovery,
not a model. Training machines can remain offline for every public read,
restart and restore operation. A bundle change is another reviewed promotion.

Tampered JSON, absent dependencies, mismatched model identity/path or persisted
model/calibrator/data bindings fail before readiness. No pickle loading or
arbitrary code execution occurs in bundle verification. The declared runtime
image must also match the promoted release receipt at review.
