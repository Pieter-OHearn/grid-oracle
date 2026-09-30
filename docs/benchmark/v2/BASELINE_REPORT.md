# WP06 v2 baseline report

Exploratory chronological reconstruction of explored 2022-2025 history. No model-promotion claims.
Deterministic orders and probability counterparts share the same WP02 targets and race cohorts.

| Horizon | Baseline | Races | Winner log loss | Brier | ECE | Rank MAE | Podium overlap | Coverage | Block loss 95% CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| pre_weekend | uniform | 70 | 2.994267 | 0.949925 | 0.000000 | 6.301840 | 0.052381 | 1.000000 | 2.992068 to 2.995732 |
| pre_weekend | standings | 70 | 1.903398 | 0.791955 | 0.021467 | 3.039921 | 0.566667 | 1.000000 | 1.773682 to 2.051165 |
| pre_weekend | recent_form | 70 | 1.954942 | 0.809062 | 0.020860 | 3.002393 | 0.519048 | 1.000000 | 1.801562 to 2.123013 |
| post_qualifying | uniform | 70 | 2.994267 | 0.949925 | 0.000000 | 6.301840 | 0.052381 | 1.000000 | 2.992068 to 2.995732 |
| post_qualifying | standings | 70 | 1.903398 | 0.791955 | 0.021467 | 3.039921 | 0.566667 | 1.000000 | 1.773682 to 2.051165 |
| post_qualifying | recent_form | 70 | 1.954942 | 0.809062 | 0.020860 | 3.002393 | 0.519048 | 1.000000 | 1.801562 to 2.123013 |
| post_qualifying | qualifying | 70 | 1.737578 | 0.748493 | 0.039199 | 2.495831 | 0.666667 | 1.000000 | 1.654670 to 1.826880 |

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
- config_sha256: `6e903cc9fed35497d3359074bd2361ac5d28c6995e1824efc6c9baa86e51b524`
- protocol_sha256: `e02b9a516d0469b90a1563e4485fd14153e907ddb09c6b8f725426124680327b`
- report_sha256: `04a025fb90b21a816e8290372ce6d066efce95ee23c4f364436fe6062a3f80e6`
- code_sha256: `f285a76b9481591117aef176afaf444d8eb1cc77e92f75fce027c88db24e2f5c`

## Committed-source reproduction and review correction

The owner approved equal mean-rank strengths on 2026-09-30; v2 was preregistered
in `6ae63cd`. Source revision: `a2a42ba48a5fe747c523c271ef88a5790fa231a4`.
Both runs started from a clean tree and produced identical source/result hashes.
This corrects an artificial tie advantage in v1; it is not model-promotion evidence.
All v1 artifacts remain preserved.

- [wp06-51c08e2ee40941ae81d738418796aee7](runs/experiments/wp06-51c08e2ee40941ae81d738418796aee7/run-manifest.json)
- [wp06-7d9f196aaf9f4224bbf6aed1671c586c](runs/experiments/wp06-7d9f196aaf9f4224bbf6aed1671c586c/run-manifest.json)

[Full compressed report](runs/experiments/wp06-51c08e2ee40941ae81d738418796aee7/report.json.gz).

Retained rejected attempts:

- [wp06-6d4506d7341c439fb3be196ee6297ada](runs/experiments/wp06-6d4506d7341c439fb3be196ee6297ada/finished.json)
- [wp06-558690fb4d154940b70a6144802c5932](runs/experiments/wp06-558690fb4d154940b70a6144802c5932/finished.json)
