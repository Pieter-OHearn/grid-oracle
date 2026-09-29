# WP06 baseline report

Exploratory chronological reconstruction of explored 2022-2025 history. No model-promotion claims.
Deterministic orders and probability counterparts share the same WP02 targets and race cohorts.

| Horizon | Baseline | Races | Winner log loss | Brier | ECE | Rank MAE | Podium overlap | Coverage | Block loss 95% CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| pre_weekend | uniform | 70 | 2.994267 | 0.949925 | 0.000000 | 6.301840 | 0.052381 | 1.000000 | 2.992068 to 2.995732 |
| pre_weekend | standings | 70 | 1.948304 | 0.797595 | 0.020552 | 3.039921 | 0.566667 | 1.000000 | 1.793508 to 2.137442 |
| pre_weekend | recent_form | 70 | 1.955447 | 0.809288 | 0.020552 | 3.002393 | 0.519048 | 1.000000 | 1.801842 to 2.123391 |
| post_qualifying | uniform | 70 | 2.994267 | 0.949925 | 0.000000 | 6.301840 | 0.052381 | 1.000000 | 2.992068 to 2.995732 |
| post_qualifying | standings | 70 | 1.948304 | 0.797595 | 0.020552 | 3.039921 | 0.566667 | 1.000000 | 1.793508 to 2.137442 |
| post_qualifying | recent_form | 70 | 1.955447 | 0.809288 | 0.020552 | 3.002393 | 0.519048 | 1.000000 | 1.801842 to 2.123391 |
| post_qualifying | qualifying | 70 | 1.737590 | 0.748496 | 0.039199 | 2.495831 | 0.666667 | 1.000000 | 1.654681 to 1.826903 |

Deterministic probability losses: **N/A** (orders do not assert probabilities).
As-of winner log loss: **N/A**; **0 / 70** diagnostic outer races satisfy the as-of contract.
Prospective winner log loss, coverage and uncertainty: **N/A** (enrollment pending).

The compressed JSON report (`report.json.gz`) contains per-race predictions, target/cohort hashes,
folds, metric denominators,
calibration bins, missing-feature counts, excluded ranking entries, all paired race/block intervals,
and circuit/season/era/driver/team/field-size/missingness slices. All entrants stay in winner fields.

The separate descriptive audit reproduces 91 qualifying-order races and 92 grid-order races.
Its provider numeric-order targets differ from this report; the figures cannot establish uplift.

No fitted challenger or calibrator was trained. Baseline parameters and tolerances are preregistered.
Unknown historical availability, reconstructed entry lists, race-only standings and weather absence
limit this report to diagnostics. Small and overlapping slices cannot justify promotion.

## Reproduce

```sh
UV_CACHE_DIR=/tmp/gridoracle-uv-cache uv run --offline --frozen --extra pipeline --group dev \
  python -m pipeline.benchmark run --output /tmp/gridoracle-wp06
```

Every attempt gets a new append-only experiment directory; compare semantic report hashes.

## Artifact hashes

- dataset_sha256: `21153f3a012bede74987f713d37e8100b2d556f60ffbcced5ca3a578c0c577a2`
- split_sha256: `0cce74e9da0a6e72e75c982c832fdf441b589641cb29872c762b543e061e89aa`
- config_sha256: `ae23f6654319f2457e52c89972bd4f693f62d005e25b8d72b8b4f701030865d6`
- protocol_sha256: `e93c19e079501313bd8839dd5b2202f0d6aa42ba0a104a4353fe5929b63cb345`
- report_sha256: `3fb827849bba7a649b920dab6a31cd7c40de79e2f761e82a075badb77ef23d6d`
- code_sha256: `1b1776a92f192ff5bf6c8d421397bf31dfd9e5608b7833305167ea9a9b9f65a0`

## Committed-source evidence

Source revision: `f624c1486ba8886399729d73699668ccf487ad89`. Both runs began with a clean working tree.

- [wp06-b77b5823cbd84e27a0d8d1a1182d91ef](runs/experiments/wp06-b77b5823cbd84e27a0d8d1a1182d91ef/run-manifest.json)
- [wp06-64cc925d647b4c0a86268dd3ec396715](runs/experiments/wp06-64cc925d647b4c0a86268dd3ec396715/run-manifest.json)

Both runs produced the same source and report fingerprints. The complete numerical artifact is
[losslessly compressed JSON](runs/experiments/wp06-b77b5823cbd84e27a0d8d1a1182d91ef/report.json.gz).

The intentionally rejected future-target experiment remains in the registry as a failed attempt.
