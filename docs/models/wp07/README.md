# WP07 classical forecast challengers

The [preregistered model cards](MODEL_CARDS.md) and [study config](config.json)
were committed in `08f502d` before implementation and scoring. They consume the
unchanged [WP06 v2 protocol](../../benchmark/v2/PROTOCOL.md), not the legacy
trainer or real bootstrap. No providers, databases, serving changes or deployment.

From the repository root, reproduce in a fresh output directory:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
UV_CACHE_DIR=/tmp/gridoracle-uv-cache \
uv run --offline --frozen --extra pipeline --group dev \
  python -m pipeline.challengers --output /tmp/gridoracle-wp07
```

Each command creates a new `experiments/wp07-*/` attempt before validation,
followed by prepared/finished events. Partial and failed trials are retained;
a crash leaves an unfinished attempt. Do not overwrite/delete experiment directories.
The CLI pins the preregistered study file hash and rejects frozen benchmark drift.
A changed study needs a separately recorded study revision, not an overwritten run.

Each successful run includes:

- `selection.json`: tune-only nominees, finalized before outer scores.
- `trials/*.json`: all 189 bounded trial configs, losses/failures and compute.
- `models/*.json.gz`: 63 selected refit artifacts, including one-hot vocabularies,
  medians/scales, XGBoost JSON weights or PL coefficients, calibration powers,
  fit row/race hashes and optimizer diagnostics. JSON is data, with no pickle.
- `report.json.gz`: all 21 candidate/ablation scorecards on each applicable horizon,
  raw/calibrated/deterministic metrics, per-race outputs and target/cohort hashes,
  reliability, whole-race slices, paired intervals and frozen guardrail diagnostics.
- `report.md`: compact per-horizon scorecard.
- `run-manifest.json`: code-file/dependency/data/config/report/model-file hashes,
  source revision/dirty state, seeds, CPU/library/thread metadata and cost timings.

Semantic hashes exclude volatile timings/IDs. Model-file hashes cover compressed
bytes; artifact hashes cover canonical uncompressed JSON. Reload with
`ForecastModel.restore(artifact['model'])`; use `predictions` and the retained
`decoder['power']` for identical inference on checksum-verified feature frames.
Every outer fold is a distinct artifact; none is a selected production refit.

Run focused tests:

```sh
UV_CACHE_DIR=/tmp/gridoracle-uv-cache uv run --offline --frozen --extra pipeline --group dev \
  python -m pytest pipeline/tests/test_challengers.py pipeline/tests/test_benchmark*.py -q
```

Research is explored reconstruction with zero as-of coverage. There is no verified
reserve designation or actual grid/weather/practice/tyre data; the report marks
those gaps explicitly. Four calibration races per fold are weak evidence.
Independent WP09 review and prospective WP15 collection remain outstanding.
No deployed incumbent artifact was supplied; comparisons against it remain N/A.
Attribution/licensing follow the [WP05 data card](../../datasets/WP05_DATA_CARD.md)
and [Jolpica evidence archive](../../evidence/README.md#attribution-and-license).
