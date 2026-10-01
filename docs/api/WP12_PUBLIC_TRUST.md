# Public forecast trust — WP12

This read-only extension consumes integrated WP06/WP09/WP11 evidence. It does not
select a champion, publish/revise forecasts, migrate/backfill data or deploy.
The approved reference remains unchanged. Public JSON schemas and TypeScript
DTOs are generated from `api/schemas/public.py`.

## Resources and information boundaries

| GET resource | Meaning |
| --- | --- |
| `/api/v1/performance/historical` | Bundled allowlisted projection of the final retained WP09 stored evaluation |
| `/api/v1/seasons/{year}/performance?horizon=…` | Every indexed event, including missing publication/evaluation, plus correction histories for one horizon |
| `/api/v1/seasons/{year}/events/{id}/performance?horizon=…` | Evaluations of that event's approved run, bound to exact result revisions |

Historical summary uses all 70 evaluation races per horizon across 2023–2025;
it is not an aggregate for the navigation season. All 32 horizon/model variants,
poor races, true round gaps, metric denominators and empty reliability bins are
preserved. Classification counts and missing feature cells remain visible.
No race is dropped because a result was poor. The archive was explored and its
source/entry availability is unverified: out-of-sample relative to fitted
weights, exploratory chronology, **not** a pristine holdout, verified as-of
evaluation or prospective performance. Baselines were retained; no challenger
was promoted. Verified as-of coverage is zero of 70 races per horizon.

`api/data/historical-performance.json` is produced by
`python -m scripts.generate_public_performance`. The generator verifies the
retained report's exact semantic SHA-256
`e1c5d0fd6b002e48a10a428b27f64348b72be217cd86e97720d4a9cc4d9c99c7`
before allowlisting. It copies stored metrics, counts, per-race scores and
winner-reliability bins; it does not recompute scores or retrain anything.
The bundled API data is included by the existing `COPY api` image instruction,
without shipping private research reports. `--check` detects drift. Equality
checks cover every score, race and reliability bin, not just rounded examples.

Live-issued evidence reads only WP03 approved publications with WP11's
eligibility/entry projection. Unknown/observed timing is not independently
verified prospective enrollment. There is no new prospective aggregate: no
valid stored cohort aggregate exists, and the browser must never calculate one
from race rows. Legacy-unverified and unpublished outputs/evaluations stay out.
All indexed weekends remain inspectable, including missed issuance and missing
results. Result revision 3 with no evaluation never displays revision 2's score
as the corrected score. Earlier evaluations remain available and labelled.

## Stored public evaluation contract

An offline **server evaluator**, not a browser, must calculate and append an
immutable WP03 evaluation for the exact `forecast_run_id` and
`result_revision_id`. Opt-in to WP12 meanings with
`evaluator_manifest.public_contract = "wp12-v1"`. Store this shape in `metrics`:

```json
{
  "values": {"winner_log_loss": 0.5, "winner_hit": 0.0, "top3_overlap": null},
  "observations": {"winner_log_loss": 1, "winner_hit": 1, "top3_overlap": 0}
}
```

This is a format example, not measured performance. Supported keys and exact
metric meanings are in `api/services/trust.py` and the public glossary:
`winner_log_loss`, `winner_hit`, `winner_brier`, `rank_mae`, `rank_correlation`,
`top3_overlap`, `top10_overlap`, `ece`. Numeric values must be finite and valid
for their unit. Missing/zero observation counts yield null, never fabricated
performance. Actual zero with a valid count is retained. Generic WP03/legacy
metrics without this version are withheld rather than guessed. The new contract
does not assert that legacy producer semantics match WP06. An evaluator opting
in must use the frozen WP06 metric/target policy, with no invented probability
from rank scores. This package creates no production evaluation or producer job.

The public projection joins the forecast's event to the result's event and
returns only the run ID, revision number, evaluation time and allowlisted scores.
It withholds evaluator IDs, manifests, paths, hashes, raw errors and unknown JSON
keys. Result source/reason fields are internal free text; only controlled
initial/correction labels and official flag/timestamps cross the boundary.
The underlying schema has no version-bound per-entry classification payload, so
this view compares stored outcome scores rather than inventing corrected driver
classification tables from mutable legacy `race_results`.

## Forecast explanation and comparison

`PublishedRun.source_name` uses a fixed recognized-provider map (Jolpica,
FastF1, Open-Meteo, OpenF1 or explicit synthetic fixture); unknown provider strings
remain null. Names do not imply those providers fed the research report.
Run context shows the original source availability, cutoff, actual issuance,
horizon, provenance and probability coverage. Historical timestamps are not
aged into false staleness. Horizon copy describes allowed input information;
no unverified per-feature attribution or production model identity is invented.
The public model/calibration cards describe measured research selection, explicitly
separate from a model-specific card for an arbitrary published run.

Official winner is the only approved probability outcome. Conditional fixed-field
rank/top-k simulations, official podium/top-ten, points and retirement probability
outputs remain withheld/unavailable. A winner-probability bar distribution has
an equivalent full-field semantic table and is loaded only on explicit request.
Exact-position accuracy is unavailable in the frozen benchmark; official top-k
set overlap measures membership regardless of order. Neither is mislabeled as
overall accuracy or individual top-k probability.

Comparison uses only approved immutable runs. The current WP03 publication table
permits one run per event/horizon, so this package cannot expose unpublished
same-horizon revisions as approved history. Select the available runs, inspect
their IDs/timestamps and compare original values. An entry-revision/field change
suppresses deltas without dropping entries or renormalizing. Both missing values
and missing runs suppress deltas. Reference win chance 0.20 and comparison 0.25
produce **+5.0 percentage points**; reversing them gives **−5.0 percentage points**.
A change is not a causal explanation. Zero remains distinct from Unknown.

## Verification and rollback

API and frontend tests, evidence-equality/generator checks, Playwright journeys,
axe WCAG A/AA and screenshot review are recorded in
[WP12 evidence](../design/evidence/wp12/README.md) and
[the package state](../workplans/WP12.md). Browser fixtures are explicitly synthetic;
only the historical scorecard uses real retained stored research evidence.
No native assistive-technology or live-provider verification is claimed.

Rollback by reverting WP12 public read views/DTO additions and rebuilding the
prior application. Keep all forecast/result/evaluation history intact. There is
no migration downgrade, deletion or release/deployment step.
