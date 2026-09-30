# WP09 calibrated model selection

WP09 compares the immutable WP07 and WP08 contenders with all required WP06 v2
baselines. It keeps the preregistered standings fallback before the weekend and
qualifying fallback after qualifying. Existing serving and its unidentified
incumbent remain unchanged. An inconclusive/noneligible challenger does not win
by being newest or by having the lowest explored-history loss.

Use the existing separate WP08 research environment; do not modify `uv.lock`:

```sh
MPLCONFIGDIR=/tmp/wp09-matplotlib OMP_NUM_THREADS=1 \
  /tmp/gridoracle-wp08-venv/bin/python -m pipeline.selection --output /tmp/wp09
/tmp/gridoracle-wp08-venv/bin/python -m pytest pipeline/tests/test_selection.py -q
```

Each invocation writes a new append-only run with a source/version/input manifest,
started and finished/failed records, compressed full report, readable selection
report, count-labelled reliability diagrams and a retention/promotion record.
A crash without a finish remains an incomplete attempt. Source changes during a
run fail it. `input-lock.json` pins upstream source, configs, models and reports;
it does not replace or modify WP06's lock. `policy.json` fixes fallback identities,
simulation seed/budget and interpretation. This policy was created after viewing
upstream diagnostics; it is **not** claimed to preregister a new statistical study.
No new candidate or promotion metric is tuned here.

The `Candidate` interface accepts one immutable `Field` and its feature rows and
returns the existing order/winner contract. `Classical`, `Custom` and `Baseline`
adapters check the artifact hash, horizon, cutoff and exact entrant field. Custom
inference imports optional PyTorch only on demand. Replay permits absolute winner
probability drift up to 2e-7 between a single-race CPU float32 matmul and WP08's
retained batched inference; exact field/order and calibration selection are
required. This is a numerical tolerance, not a changed WP06 promotion tolerance.
All source probabilities are still validated by the unchanged WP06 rules.

The full report contains every WP07 full/ablation model, both WP08 families and
all three/four required baselines; no silent race intersections. Pairwise scores
are recomputed using the frozen evaluator and paired race/four-race bootstrap.
Every WP07 predeclared slice (including corrected fitting-exposure flags) remains
in its guardrails; WP08 retains its registered WP06 slices. Baselines are scored
on the same whole race/entry/target cohorts. Incumbent comparison remains N/A.

## Output meaning

Winner calibration replays the original bounded power/temperature choices on
predictions of four earlier, held-out calibration races after fixed weight fits.
The adapter rejects training/calibration overlap, changed targets, partial blocks
and late label timestamps. These are out-of-sample forecasts relative to fitted
weights, but the archive's input/entry availability is unverified. Historical
cutoff markers are preserved verbatim and never replaced with invented dates.

`coherent_output` preserves calibrated winner probabilities. It samples a joint
Plackett–Luce suffix for each possible winner and weights those permutations by
that winner's exact probability. Derived rank and top-k marginals share the same
weighted draws, are nested, and have fixed-field slot sums. Sampling variation is
reported separately from model uncertainty. Exact winner probabilities do not
inherit Monte Carlo noise. Zero-strength entrants are ordered uniformly after
positive-strength entrants in the limiting conditional PL distribution.

The target is **conditional on the fixed field completing**. This distribution
has no DNS, DSQ or retirement mechanism. Conditional top-three/top-ten are not
official podium/top-ten estimates and are not public-display approved. Official
top-k, points and retirement fields are null. Supplemental conditional reliability
uses fully classified fields only and reports excluded race counts; it cannot
establish official-event calibration. Only sub-1e-10 summation roundoff at probability zero/one is bounded in derived
marginals; invalid inputs fail and winner/scoring probabilities are never repaired.
Winner reliability uses every eligible
entrant, WP06 equal-race weights and ten fixed bins, with entry/race counts.

Changing an entry, constructor assignment, cutoff, horizon or revision requires a new field/run identity.
Reordering the same input field does not alter its simulation. Never drop a late
withdrawal and silently renormalize a saved forecast. Preserve its original field
and issue a separately identified revision when an authorized publication path
supports it. WP09 does not alter WP03's immutable publication table semantics.

`store_research_output` integrates with WP03 manifests and immutable entry rows;
it always marks these research runs `legacy_unverified`, which cannot publish.
It persists complete expected outputs plus field/output hashes and artifact
lineage, so retries reproduce and entry revisions cannot overwrite old outputs.
This is additive code, with no database migration or live database write.

## Manual selection and rollback

`pipeline.selection.ledger.Ledger` is an optional local operator ledger, not a
production API or authentication system. The named local operator/reviewer is a
trusted assertion. It appends hash-chained events with file locking and a required
expected-head token; callers must handle stale-head errors rather than overwriting.

- `register` records immutable model/calibrator/config/data/split hashes as proposed.
- `challenge` requests review without changing the active pointer.
- `approve` requires a separate named reviewer, an audit reference, a passing
  unchanged WP06 gate, and binding to the exact candidate and current incumbent.
- `promote` is a separate explicit operator action; insertion and approval do not
  switch the pointer automatically. The old champion becomes retired.
- `rollback` explicitly points to a prior champion of the same horizon, preserving
  every old event and forecast. A never-selected contender cannot be a rollback.

When no pointer exists, an explicit `bootstrap` can record only the fixed horizon
baseline. It is not evidence of statistical qualification. This implementation
has not created a serving pointer. The retained promotion record is a decision
to keep the baseline, with `promoted: false` for each horizon. Operational use,
prospective enrollment, independent review and actual publication remain later
steps under the existing workplans.

## Retained review evidence

- [Selection report](REPORT.md), [model card](MODEL_CARD.md), [calibration card](CALIBRATION_CARD.md).
- [Validation summary](validation/SUMMARY.json) and [training reproduction](validation/training-reproduction.json).
- Final runs: [first](runs/wp09-0762031a4c934b9e900160435be657ca/manifest.json)
  and [repeat](runs/wp09-db775b5e89324234a4c4e6438908dd24/manifest.json), both
  measured at `93f3fe0` with matching semantic report hash
  `e1c5d0fd6b002e48a10a428b27f64348b72be217cd86e97720d4a9cc4d9c99c7`.
- [Pre-weekend reliability](runs/wp09-0762031a4c934b9e900160435be657ca/reliability-pre_weekend.png)
  and [post-qualifying reliability](runs/wp09-0762031a4c934b9e900160435be657ca/reliability-post_qualifying.png).

Run `python -m docs.models.wp09.verify_artifacts` to check the retained hashes,
measured source revisions, current source and matching final reports. All seven
WP09 attempts are retained. The dirty development run and earlier clean pairs
are explicitly superseded in `retention.json`; do not consume those outputs.
The complete reports intentionally include every conditional marginal, so their
compressed JSON files are larger than the earlier winner-only studies.
