# Offline benchmark (WP06)

The active protocol is [v2](v2/PROTOCOL.md), preregistered with owner approval
in `6ae63cd` before corrected baseline execution. [V2 config](v2/config.json)
and [lock](v2/lock.json) retain all v1 metrics and promotion tolerances while
correcting tied scores to equal mean-rank probability strengths. Deterministic
orders still break ties by driver ID. See [review fixes](v2/REVIEW_FIXES.md).

V2 reuses the exact frozen [dataset](dataset.json) and [splits](splits.json).
The original v1 protocol/config/lock, [v1 baseline report](BASELINE_REPORT.md)
and all experiments remain preserved. They are historical evidence of the
superseded behavior, not eligible comparators for new work. Use the
[v2 baseline report](v2/BASELINE_REPORT.md) for current diagnostics. To reproduce
v1 for audit, check out its recorded source revision; the current CLI uses v2.

From the repository root, after the WP01 environment setup:

```sh
UV_CACHE_DIR=/tmp/gridoracle-uv-cache uv run --offline --frozen --extra pipeline --group dev \
  python -m pipeline.benchmark run --output /tmp/gridoracle-wp06
```

This reconstructs and verifies all WP05 partitions, reproduces the earlier audit,
scores the fixed baselines and writes a report path. It never contacts providers,
fits challengers, accesses a database or changes the active model. Every attempt is registered before config parsing, checksums or dependency discovery. It
has a unique `experiments/wp06-*/` directory with started/prepared/finished events, exact
code/config/dependency hashes, seed, Python/package versions and compute metadata.
Errors become failed events; interrupted runs remain visibly unfinished. Keep the
output root on durable storage for research; `/tmp` is a reproduction example.

`report.json.gz` contains per-race outputs, summary/fold/slice metrics and paired
uncertainty; `report.md` is the compact scorecard; `run-manifest.json` records
volatile execution metadata separately. The JSON is losslessly gzip-compressed
with fixed timestamps; its semantic hash covers the uncompressed canonical bytes. Compare the semantic `report_sha256`
between repetitions. The canonical JSON hash excludes timestamps and compute.
The config's **file hash** is the lock identity; an earlier development run also
recorded its canonical JSON hash, explicitly retained in the run history.

WP05 has no eligible as-of rows. As-of results are N/A with zero eligible coverage;
prospective results are N/A with enrollment pending. The 70 diagnostic evaluation
races are 2023–2025, using 2022 onward for prior training/tuning/calibration blocks.
All 92 source races remain in the frozen dataset. A missing qualifying feature
uses the preregistered fallback and remains visible, rather than dropping a race.
Uniform calibration ECE can be zero by construction; that is not evidence of a
useful predictor. Brier/log loss and discrimination guardrails must also pass.

## Consumer interfaces

- `evaluation.evaluate_predictions`: accepts `{race_key: {order: [...], winner:
  {driver_id: probability}}}` plus frozen targets/dataset/splits/config. Omit
  `winner` for a deterministic order. Rejects unknown races, changed target
  hashes, missing entrants and invalid probabilities. A completely missing
  race is counted in scheduled coverage and receives an explicit failure reason.
- `uncertainty.uncertainty`: pairs only identical ordered race, entry and target
  cohorts. It will not silently intersect missing forecasts. Original block
  identifiers survive slices; gaps never collapse into fictitious adjacent races.
- All public evaluation and fitting adapters verify dataset, splits and optional
  config against the registered lock. Caller-defined re-freezes, changed labels
  or smaller evaluation denominators are rejected. Evaluation outputs include
  input fingerprints. Omitting a fitting config selects the registered one.
- `fitting.fit_in_block`: permits only train or explicit train+tune refit. Tuning
  is scoring-only; feature models cannot use calibration rows. Duplicate columns
  are rejected and feature values must match checksum-verified WP05 partitions.
  Labels are supplied separately and checked against immutable source targets.
  `target_kind="winner"` is the default; `"rank"` means contiguous classified
  ranks with missing labels for unclassified entrants.
- `fitting.fit_calibrator`: accepts base-model winner probabilities and binary
  winner labels only from a calibration block, with whole-field and coherence
  checks and verified winner labels. Any supplied `available_at` must precede
  the pinned first evaluation race, even when no caller cutoff is supplied.
  Optional caller cutoffs must equal that deadline. Baselines use identity
  calibration and do not invoke it.
- `temporal.validate_features(..., evidence=..., dataset=...)`: validates as-of provenance,
  including entry-list and feature event/publication/retrieval times. Proof race
  and first-session times must match the pinned race record. The current archive
  has no verified first-session timestamps and cannot pass this as-of gate. The
  exploratory path without evidence cannot confer as-of eligibility. Consumers
  must supply verified source evidence; self-asserted timestamps are not proof.
- `promotion.review_gate`: returns reasons or eligibility for **independent
  review**, always `promoted=false`. It has no production writer, registry
  “latest” selector or deployment call. Reviewers verify the evidence bundle;
  Boolean attestations are a checklist, not cryptographic authorization.

WP07/WP08 should use these interfaces and frozen contracts. They are not started
by WP06. WP09 owns reviewed selection and WP15 prospective collection/operation.
This CLI intentionally cannot upgrade archived data to as-of status. New verified
datasets/calendar enrollments require separately reviewed, additive manifests
before their evaluation, retaining v1 and all earlier experiments.

## Artifact retention and checks

Run `python -m pytest pipeline/tests/test_benchmark*.py -q` inside the pinned
pipeline environment. `make check`, `make test`, and `cd dashboard && bun run build`
are the repository gates. Frozen manifests can be regenerated only into a new
version; the `freeze` registration command refuses to overwrite existing files. Named
artifacts serialize first and use fsync plus atomic no-overwrite publication.
If failure recording itself fails, the original exception survives with a note
and the started event remains unfinished.
No database migration or production rollback is required. Stop selecting this
benchmark version to roll back; retain every experiment, including failures.

Derived data retain the source archive's attribution and licensing; see
[the evidence archive terms](../evidence/README.md#attribution-and-license).
Application code licensing is unchanged. The source is Jolpica-F1, retrieved
2026-09-28; derived diagnostic scores do not imply provider endorsement.
