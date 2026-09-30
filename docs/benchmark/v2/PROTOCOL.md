# WP06 benchmark protocol v2

This protocol and [configuration](config.json) are committed before challenger
experiments. They are evaluation rules, not a model-promotion claim. A later
change requires a new protocol, an explicit rationale and fresh prospective
evidence. Never adjust v2 tolerances after viewing challenger evaluation results.

## Data, targets and information boundaries

Pin WP05 dataset manifest
`6ff6b63b470900cb1d55513d91e9362851948d04133b8cd2b216bb7dccf671d2`,
its raw snapshots, feature contract and each partition checksum. Reconstruct
from the committed archive; reject drift. Labels live separately from features.
Use WP02 target policy `2026.1`: winner and official top-3/top-10 membership
come from eligible official classified ranks; ranking metrics compare contiguous
ranks **within classified entrants**, including classified retirements. DNS,
DSQ, unclassified and unknown statuses have no internal ranking label. All
intended entries remain in the winner probability denominator. Never substitute
provider numeric result order or final grid for these targets/features.

Pre-weekend features exclude current qualifying. Post-qualifying uses verified
qualifying, never retrospectively recorded final-grid data. Feature inputs are
allowlisted by horizon; targets and unknown columns are rejected. As-of mode
also requires entry provenance, cutoff and per-feature event/publication/retrieval
timestamps; everything must be known by cutoff. History events must precede the
current race weekend; qualifying must precede the post-qualifying cutoff. Final
qualifying/grid readiness and issuance before race start are required for that
horizon. Calibration labels must be available before outer evaluation starts.

The entire 2022–2025 archive has been explored. Its source availability and
entry-list publication times are unverified. It supports **exploratory
chronological reconstruction only**, with as-of metrics N/A and explicit zero
as-of coverage. It is neither a pristine holdout nor prospective evidence.

## Frozen splits and fit scope

Outer diagnostic folds evaluate all races of 2023, 2024 and 2025 respectively.
For each fold, only earlier seasons form the fitting pool: its last four races
are calibration, preceding four are inner tuning, all earlier races are inner
training. Training, tuning, calibration and evaluation are ordered disjoint
whole-race blocks. A model may refit on training+tuning after choosing its
configuration; it may never fit features/transforms/weights on calibration or
evaluation. A calibrator may fit only the calibration block after weights and
configuration are fixed. Baselines have fixed parameters and identity
calibration, and consume no fitting labels. Earlier held-out outcomes may feed
later races' lagged features only after their publication; evaluation never
changes fitted weights/configuration. Fit-scope validation applies to supplied
row IDs, not merely caller-provided block names.

## Baselines and paired cohorts

Both horizons include a uniform winner distribution, race-only standings order,
and recent classified driver/constructor form (equal mean of the two available
last-three averages). Post-qualifying also includes qualifying order. Missing
form/qualifying falls back to race-only standings then the field midpoint.
Driver identity breaks ties only for the deterministic order. The probabilistic
counterpart uses fixed Plackett–Luce strengths `exp(-mean_tied_rank / 4)`, where
ranks are zero-based and tied scores share the arithmetic mean of their occupied
ranks. Winner probabilities normalize those strengths; uniform uses equal
strengths. Equal scores therefore always have equal winner probabilities,
including season-opening standings ties.
No parameter search and no learned calibration occur in WP06. Deterministic
orders have N/A probability losses; probabilistic variants share their order.
WP06 scores winner probabilities and deterministic top-k sets, not invented
podium/top-ten probability estimates or points/DNF probabilities.

All contenders in a comparison must predict exactly the same race/entry cohort,
including the intended field and target hash. Missing predictions are explicit
coverage failures. A common-cohort comparison may be diagnostic, but cannot
silently shrink its scheduled denominator or qualify for promotion. Whole-race
exclusions, failure reasons and missing feature/target counts remain visible.

## Metrics, numerical policy and uncertainty

Primary selection metric: equal-race mean winner negative natural log likelihood
(lower is better). Secondary: winner hit, classified-rank MAE, Spearman rank
correlation, official podium/top-ten set overlap, multiclass winner Brier score
(sum across the field), ten fixed equal-width bin winner calibration/ECE and
coverage. ECE uses every entrant with weight `1 / field_size`, then equal race
weight. Report reliability-bin weight, predicted probability and observed rate.
Top-k overlap divides by the number of observed eligible official top-k finishers;
missing/ambiguous winner or top-k labels yield N/A rather than zero. Metrics
with no observations return JSON null and render **N/A**. Counts and denominators
are always reported. Ranking requires two classified entrants for correlation.

Reject nonfinite probabilities, negatives, values above one or field sums more
than `1e-10` from one. Valid zero/one distributions are permitted: for log loss
only, clamp the true winner probability to `[1e-15, 1]`. Thus a certain correct
prediction has loss 0, a zero assigned to the winner has loss 34.5387763949.
Do not clip/renormalize probabilities for Brier, calibration or coherence checks.
This avoids infinite arithmetic without concealing overconfident mistakes.

Use 2,000 seeded paired bootstrap draws over races and non-overlapping consecutive
four-race blocks **within outer folds**, retaining the final short block.
The same sampled indices apply to both contenders. Report mean loss, 95%
percentile loss interval and paired improvement (`reference - candidate`) for
both resampling units. Resample whole races, never drivers. Block intervals are
the primary uncertainty guardrail; race intervals are sensitivity diagnostics.
Fewer than two independent units yields N/A. Small slices are descriptive.

Slice by season (era proxy; this archive covers only the 2022–25 regulation era),
circuit, field size, missing-history/qualifying and weather-free cohorts. Driver
and team reports use races in which that entity entered, preserve the entire
race field, and overlap intentionally; they are not driver-level winner losses.
Never select a model by searching the best slices.

## Locked promotion tolerances

The numeric values in config.json are binding. Require at least 40 prospective
races and 10 blocks on a complete locked cohort; mean winner log-loss improvement
at least 0.01 nat and paired block 95% lower bound strictly above zero **against
both the preregistered strongest eligible baseline and incumbent**. Comparator
identities must be selected using training/tuning evidence before evaluation.
No comparator selection using these diagnostic test scores.

Against each comparator: MAE regression ≤0.10, rank correlation drop ≤0.02,
podium/top-ten overlap and winner hit drop ≤0.02, Brier increase ≤0.005,
ECE increase ≤0.01 and absolute ECE ≤0.05. Coverage ≥95% and no decrease;
all required score cohorts identical. Every predeclared slice with ≥10 races
must have log-loss regression ≤0.10. Probabilities must be coherent and finite;
CPU inference ≤2 seconds/race, peak process RSS ≤1,024 MiB, and ≥6 operational
shadow races. Shadowing measures operation, not statistical confidence.

A gate emits reasons and **review eligibility only**, never an active model.
An explicit independent WP09 review/approval and separate publication action
remain mandatory. Missing metrics, unresolved failures, incomplete prospective
data or inconclusive uncertainty fail closed. Experiment insertion time has no
selection meaning. The registry has no promote/latest-wins operation.

## Genuinely future evaluation

Reserve all officially scheduled Grand Prix events in calendar years **2027 and
2028** as a consecutive prospective window after this protocol's 2026-09-29
registration. No 2022–2025 race can enter it. Exact race identities must be
committed from a versioned calendar at least 30 days before the first event of
each season; predeclare schedule revisions and retain cancellations/missed
issuances in coverage. No race may be enrolled after its first competitive
session. The policy is frozen now; actual enrollment is **pending**, not a
fabricated dataset. Prospective report values remain N/A today.

Freeze contender code, weights, calibration, comparators, target/split/config
hashes and prediction outputs before issuance deadlines. Record every scheduled
issuance and failure. No challenger tuning or discretionary re-selection using
these outcomes. A changed model starts a new preregistered future window. At the
end of the fixed window, if minimum sample/guardrails fail, retain the incumbent
or eligible baseline; do not extend the window opportunistically for significance.
WP15 operates the shadow window; WP06 implements no scheduling or deployment.

## Registry, reproducibility and rollback

Every run records protocol/dataset/split/config/code/dependency hashes, git
revision and dirty state, Python/library versions, seed, CPU/platform, thread
settings, elapsed time, peak RSS, status and error. Write an exclusive started
record before work, then an exclusive success or failure event. A crashed run
remains started without completion; it is not silently successful. Repeat runs
receive separate IDs; attempts and failures are never overwritten or deleted.
Reports have semantic result hashes independent of volatile compute metadata.
Git tracks the initial report and experiment events. Users must retain output
registries on durable storage for subsequent experiments.

Reproduce the prior `docs/evidence/baseline_audit.py` offline and compare its
summary excluding retrieval time. Keep it separately labelled descriptive
provider-order audit: different targets and cohorts prohibit uplift comparison.
Rollback means stop consuming v2 or revert its offline code. Preserve all
protocols, frozen inputs, reports and unsuccessful experiments. No runtime model,
real database, homelab infrastructure or deployed service changes in WP06.

## Owner-approved v2 correction (2026-09-30)

The owner explicitly approved mean-rank ties for PR #99 finding A1 on 2026-09-30,
before v2 baseline execution. The v1 identity tie-break assigned different
probabilities to equal scores. V2 corrects that artificial advantage; this is
not a challenger improvement or evidence for promotion. V1's protocol, config,
lock, dataset/split manifests and every experiment remain preserved. V2 reuses
the exact v1 dataset and split bytes under its own lock. All metrics, seeds,
numerical policies, promotion guardrails/tolerances and future-window policy
remain unchanged. Only protocol identity and probabilistic tie semantics change.
Fresh prospective evidence under the corrected protocol is still required.
