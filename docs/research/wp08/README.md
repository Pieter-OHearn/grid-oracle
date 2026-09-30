# WP08 offline custom ranking experiments

This is an experiment and learning track. It has no production selector, database,
API integration, automatic promotion or deployment. WP06's v2 benchmark contracts,
data, splits, metric code and guardrails are read-only. WP07 owns its separate
classical experiments. WP09 remains an independent decision/review package.

## Model and information boundaries

`RaceRanker` gives each entry a scalar log strength: horizon-specific linear
features + regularized driver/team effects + optional team/circuit interaction.
The nonlinear challenger adds a shared 8- or 16-unit tanh network. Each entry uses
the same function, so rearranging a field rearranges scores. Separate fitted
artifacts are retained for each horizon/fold/family; horizon conditioning is
explicit inside the reference and challenger, with no qualifying in pre-weekend.

The likelihood is ordinary Plackett-Luce for fully classified races. With censored
DNS/DSQ/unclassified entrants it uses a winner draw over the entire intended
field, followed by the relative order of remaining classified entrants only.
This conditional observation model does not assert an unclassified entrant
finished last. Sum observed-stage losses within each race; average equally over
races. Winner inference is softmax over all intended entrants. This ranking
objective is not identical to the selection metric, winner log loss, and may
trade off winner accuracy for full classification fit. No podium, DNF or points
probability claim is made.

Driver, team and circuit dictionaries are fit only on allowed training rows.
Unknown identities map to protected zero effects; known lagged features still
apply. Circuits use only WP06's pinned manifest metadata. Fixed feature scale is
22 and fixed missing-rank midpoint is 11.5, with missingness flags. This scale is
not a fixed field-size restriction: masks work with 20, 22 and other field sizes.
Driver/team contributions are partially confounded; L2 shrinkage controls them,
not a claim of identified causal driver skill. No Bayesian uncertainty is claimed;
WP06's paired whole-race/block intervals remain the uncertainty method.

`config.json` preregisters the bounded experiments: 160 Adam steps per fit, seed
6062026, five reference variants and two small challenger widths. History-window,
feature-group, interaction and shrinkage choices use only each frozen four-race
tuning block. Choose by equal-race winner loss (registered-order ties), refit on
training+tuning, then choose temperature from the registered grid using only the
four calibration races through WP06's checked calibrator adapter. All decisions
are written before any outer scoring. Locked evaluation never changes settings,
weights or calibration. Exploratory results cover the identical 70 race/entry
cohorts for both horizons; as-of is 0/70 and prospective remains N/A.

## Reproduce without changing the frozen dependency lock

The tested environment is Python 3.12.14, PyTorch 2.7.0, macOS arm64. Install the
separate complete pinned Mac environment (no modification of `uv.lock`):

```sh
uv venv --python 3.12 /tmp/gridoracle-wp08-venv
uv pip install --python /tmp/gridoracle-wp08-venv/bin/python \
  -r docs/research/wp08/requirements-macos.txt
/tmp/gridoracle-wp08-venv/bin/python -m pytest pipeline/tests/test_custom_model.py -q
/tmp/gridoracle-wp08-venv/bin/python -m pipeline.custom_model.experiment \
  --output /tmp/gridoracle-wp08 --backend cpu
```

Use `--reference-only` for the initial reference track. `--backend mps`, `cuda`
or `auto` probes available devices; an explicitly unavailable backend fails and
records the failed attempt. CPU is the reproducibility reference. MPS and CUDA
use float32; probability normalization/reporting uses CPU float64 to meet WP06's
1e-10 field-sum policy. MPS CPU fallback is unnecessary: small O(field²) logsumexp
risk sets replace an unsupported torch 2.7 MPS logcumsumexp operation.

We checked the official [PyTorch installation guide](https://pytorch.org/get-started/locally/),
[MPS documentation](https://docs.pytorch.org/docs/stable/notes/mps.html) and
[reproducibility guidance](https://docs.pytorch.org/docs/stable/notes/randomness.html)
on 2026-09-30. PyTorch 2.7.0 has a native macOS arm64 wheel. CUDA builds are chosen
for the actual PC OS/GPU/driver using the official selector, not installed on this
Mac. The owner reports Ryzen 7 5700X / RTX 5060 / 32 GB / Windows 11 Pro; exact
GPU VRAM, driver and installed CUDA runtime remain unverified. The Mac lock is
not a Windows/CUDA lock. Run `hardware()` and the acceptance tests on that PC
before claiming CUDA parity; no remote host access has been inferred.

Base environment checks use `UV_PROJECT_ENVIRONMENT=/tmp/gridoracle-wp08-venv
UV_NO_SYNC=1 make check` and `make test` with the same environment variables;
ordinary base installs skip optional torch tests, while this research environment
runs them. `uv.lock` still matches WP06's frozen hash.

## Artifacts and interruption

Every attempt gets an exclusive UUID directory: started event, manifest, immutable
epoch checkpoints, curves, per-fold decisions, selection freeze, compressed full
report and finished/failed event. Started without a finished event means crashed,
not success. Atomic write-once files never overwrite an earlier attempt. Complete
runs record all artifact hashes, code/config/dependency fingerprints, hardware,
seed, thread count, runtime and peak RSS. Only scratch reconstructions may be
omitted from retained runs; their pinned manifests are already frozen in WP05.

`training.train(..., checkpoint_dir=..., stop_after=...)` saves optimizer state,
weights, vocabulary, exact batch/label/mask hash, epoch, curve, torch CPU RNG,
backend/version and source hashes. Resume with `resume=.../epoch-NNNN.pt` and the
same config, input rows and backend. A new checkpoint directory is allowed;
existing names cannot be overwritten. Tests force a child process to exit after
11 epochs and prove the resumed 30-epoch result equals an uninterrupted run
bit for bit. Training is full-batch with no dropout/shuffle or stochastic device
operations after CPU initialization; no unrecorded GPU RNG is consumed.

Parity tolerances are declared in the tests: float32 scores 2e-5 absolute/relative,
loss 2e-4 absolute + 2e-5 relative, gradients and one SGD update 2e-4
absolute/relative. CPU gradcheck uses float64 finite differences (1e-6 steps,
1e-5 absolute). These are numerical equivalence tolerances, independent of
WP06's unchanged statistical/promotion guardrails. MPS peak allocation is
sampled before backward/after optimizer steps, so it is a sampled allocator
high-water measurement, not a hardware VRAM counter. M1 memory is unified.
CUDA uses its allocator peak counter; unavailable accelerators report null.

Rollback: stop using these offline artifacts or revert the WP08-only changes.
No schema migration, backfill, bootstrap, publication or service rollback exists.

The retained comparison is in [REPORT.md](REPORT.md), with every trial's tuning
scores, frozen selections, failed experiments and compute evidence. The two clean
runs reproduce the same semantic result. Verify every original event/model/report
hash with `python -m docs.research.wp08.verify_artifacts`. Checkpoint archives are
ordinary tar.gz files; extract into a temporary directory to resume an original
checkpoint. Twelve selected final models are also loose files in the first clean
run's `models/` directory. [Loss curves](loss-curves.png) plot training+tuning
refits and must not be interpreted as evaluation winner loss.
