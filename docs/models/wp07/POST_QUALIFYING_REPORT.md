# WP07 post qualifying champion/challenger report

Exploratory chronological reconstruction of the frozen WP06 v2 cohort: 70 scheduled races, 2023–2025, 18 original four-race blocks. All entrants retained in winner fields. **As-of coverage 0/70; as-of and prospective metrics N/A. No production model selected.**

Tune-only development nominee: **xgb_regression__full**. Fixed comparator: **qualifying**. Incumbent comparison N/A: no deployed artifact supplied. The nominee uses the mean of best inner-fold full-model scores across the study, not a promise of a historical deployment decision or prospective superiority. Outer scores never revise this nomination.

## Observed result and limitations

The inner-tune nominee, XGBoost regression, improves diagnostic winner LL by
0.416577 nat against qualifying order, with paired block CI 0.184784 to 0.660135.
Ranking also improves (0.388825 nat; CI 0.222184 to 0.533298). Regression's podium
overlap drops from 0.666667 to 0.642857, exceeding the locked 0.02 tolerance;
**the nominated model therefore fails a numeric guardrail despite better loss**.
Ranking passes numeric baseline guardrails here, but this observation cannot
change the preregistered nominee or authorize a production selection. PL's full
model interval includes zero and it fails winner-hit/slice guardrails.

Qualifying contributes strongly: removing it raises LL by 0.518111 nat for
regression, 0.616564 for ranking and 0.378571 for PL; all three paired block
intervals exclude zero in the unfavorable direction. Restricting training to
the newest season hurts both tree models with negative ablation intervals.
Removing short-form recency is inconclusive across these models; PL's apparent
0.134696 nat ablation gain has an interval including zero. No variant replaces
the full model based on the outer diagnostics.

The raw regression decoder achieves 1.712555 LL versus the baseline's 1.737578;
learned calibration accounts for most of its final gain to 1.321001. Calibrated
Brier and ECE also improve, but four calibration races are not strong evidence
of transfer. All three models have higher 2024 loss than 2023; regression's 2025
loss (1.349348) is also higher than its 2023 loss (0.730796). Recent-tail scores
remain close to the other races for the trees on this horizon, unlike pre-weekend.

Known-team effects and qualifying permit complete predictions for unseen drivers,
but the 56-race cold-start/rare-entry cohort is very broad. The eight team-change
races and single missing-qualifying race cannot establish robust edge-case quality.
Missing-history performance covers ten races; regression's LL is 1.500885 there,
above its overall 1.321001. Actual reserve outcomes cannot be identified from
this dataset. No prospective, serving or future-superiority claim follows.

## Effective fitting-exposure correction

These reports use corrected source `e3484a3`, resolving the delegated review's
P2 finding. Rare-entry/cold-start exposure excludes zero-weight fitting seasons.
For every `recent_season_pool` model, 14 additional 2024 races now enter the
rare-entry slice: **56 → 70** races across the full diagnostic cohort. Ricciardo
has 3 positive-weight fitting appearances rather than 25. Full-model slice tables
below retain their original counts because full models use all fitting seasons.

Predictions, trained model artifacts, overall metrics and tune-only nominations
are identical to the initial runs. Only exposure annotations, derived slices,
related guardrail reasons and report/source fingerprints change. The removed
`rare_entry:False` guardrail failures are explained in the
[correction record](DIAGNOSTIC_CORRECTION.md). Original experiment directories are
retained; their pooled-exposure diagnostics are superseded by the corrected runs.

## Served orders and calibrated winner probabilities

| Model | LL | Brier | ECE | Rank MAE | Rho | Winner hit | Top3 | Top10 | Coverage | Loss block 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| qualifying | 1.737578 | 0.748493 | 0.039199 | 2.495831 | 0.750063 | 0.614286 | 0.666667 | 0.790000 | 1.000000 | [1.654670, 1.826880] |
| hierarchical_pl__full | 1.520181 | 0.703319 | 0.022003 | 2.345068 | 0.785106 | 0.571429 | 0.647619 | 0.792857 | 1.000000 | [1.249940, 1.818692] |
| xgb_ranking__full | 1.348753 | 0.656649 | 0.019902 | 2.457862 | 0.768573 | 0.600000 | 0.661905 | 0.800000 | 1.000000 | [1.184346, 1.543801] |
| xgb_regression__full | 1.321001 | 0.613513 | 0.010077 | 2.428201 | 0.773083 | 0.600000 | 0.642857 | 0.794286 | 1.000000 | [1.042720, 1.600302] |

Ranking labels exclude unclassified/DNS/DSQ entrants; official top-k sets remain separate. The deterministic order has N/A proper probability scores. Multiclass Brier sums over the entire field; ECE uses WP06 ten fixed bins, entrant weight 1/field size and equal race weight. Low ECE alone does not establish discrimination. Counts and reliability bins are retained in the full JSON.

## Paired uncertainty and diagnostic guardrails

| Full model | Comparator − model LL | Race CI | Four-race block CI | Nominee − model LL | Nominee block CI |
| --- | ---: | --- | --- | ---: | --- |
| hierarchical_pl__full | 0.217397 | [-0.022637, 0.450261] | [-0.051458, 0.460733] | -0.199180 | [-0.357613, -0.041749] |
| xgb_ranking__full | 0.388826 | [0.233386, 0.525279] | [0.222184, 0.533298] | -0.027752 | [-0.194337, 0.138882] |
| xgb_regression__full | 0.416577 | [0.217700, 0.603964] | [0.184784, 0.660135] | 0.000000 | [0.000000, 0.000000] |

Positive means the challenger has lower loss. WP06 2,000 paired draws, seed 6062026; whole races/blocks only, no driver resampling or silent intersections. These intervals are diagnostic on explored history; many comparisons and slices are not multiplicity-adjusted.

- **hierarchical_pl__full**: paired block improvement interval inconclusive; winner_hit_drop failed or missing; slice cold_start:False regressed or missing; slice rare_entry:False regressed or missing; slice season:2024 regressed or missing.
- **xgb_ranking__full**: passes the numeric baseline guardrails on this diagnostic cohort only.
- **xgb_regression__full**: top3_overlap_drop failed or missing.

Every candidate fails prospective review eligibility: future evidence, frozen pre-outcome issuance, incumbent comparison, operational shadow races and resource qualification remain missing. The frozen tolerances and review-gate reasons are retained, without changing benchmark rules.

## Calibration and recent-era drift

| Full model | Raw ordinal LL | Calibrated LL | Powers 2023/2024/2025 | LL 2023 | LL 2024 | LL 2025 |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| hierarchical_pl__full | 1.730447 | 1.520181 | 2.0/4.0/2.0 | 1.046343 | 2.167008 | 1.307706 |
| xgb_ranking__full | 1.687590 | 1.348753 | 2.0/4.0/2.0 | 1.046343 | 1.667008 | 1.307706 |
| xgb_regression__full | 1.712555 | 1.321001 | 4.0/4.0/2.0 | 0.730796 | 1.833675 | 1.349348 |

The shared decoder starts at mean tied rank/temperature 4, then fits one of five powers only on the four calibration races after refit. Higher powers sharpen the distribution. Baselines retain their frozen identity calibration. Thus calibrated uplift includes decoder fitting and cannot be attributed solely to architecture. Four races offer weak protection against drift; raw/calibrated reliability and proper scores are both available. The study contains one regulation era.

## Ablations (independent inner tuning; same outer denominator)

| Variant | LL | Full − variant LL | Paired block CI |
| --- | ---: | ---: | --- |
| hierarchical_pl__no_qualifying | 1.898753 | -0.378571 | [-0.592857, -0.178571] |
| hierarchical_pl__no_recency | 1.385486 | 0.134696 | [-0.005779, 0.260310] |
| hierarchical_pl__recent_season_pool | 1.448753 | 0.071429 | [-0.031337, 0.183824] |
| xgb_ranking__no_qualifying | 1.965317 | -0.616564 | [-0.916591, -0.359469] |
| xgb_ranking__no_recency | 1.342628 | 0.006124 | [-0.200215, 0.209905] |
| xgb_ranking__recent_season_pool | 1.633174 | -0.284421 | [-0.414860, -0.162224] |
| xgb_regression__no_qualifying | 1.839112 | -0.518111 | [-0.702446, -0.308567] |
| xgb_regression__no_recency | 1.385024 | -0.064023 | [-0.277001, 0.139858] |
| xgb_regression__recent_season_pool | 1.497595 | -0.176594 | [-0.304296, -0.046630] |

`no_recency` removes short-form means/counts/reliability and disables age weighting, while preserving season standings, identities and missing flags. `recent_season_pool` gives older fitting seasons zero weight: this is a season-pooling test within one regulation era. `no_qualifying` removes current qualifying and its missing flag in the post-qualifying horizon only. Grid, weather, practice and tyre ablations are **N/A** because no valid registered data exists. No legacy proxies or final-grid values were imported.

## Cold starts, reserves, team changes and missing data

| Slice | Full model | Races | Winner LL | Comparator − model | Block CI |
| --- | --- | ---: | ---: | ---: | --- |
| cold_start:True | hierarchical_pl__full | 56 | 1.374843 | 0.359190 | [0.089472, 0.589467] |
| cold_start:True | xgb_ranking__full | 56 | 1.303415 | 0.430619 | [0.260961, 0.585066] |
| cold_start:True | xgb_regression__full | 56 | 1.268725 | 0.465308 | [0.171070, 0.744943] |
| rare_entry:True | hierarchical_pl__full | 56 | 1.374843 | 0.359190 | [0.089472, 0.589467] |
| rare_entry:True | xgb_ranking__full | 56 | 1.303415 | 0.430619 | [0.260961, 0.585066] |
| rare_entry:True | xgb_regression__full | 56 | 1.268725 | 0.465308 | [0.171070, 0.744943] |
| low_experience:True | hierarchical_pl__full | 19 | 1.573853 | 0.204389 | [-0.306242, 0.593906] |
| low_experience:True | xgb_ranking__full | 19 | 1.547537 | 0.230705 | [-0.166498, 0.515933] |
| low_experience:True | xgb_regression__full | 19 | 1.426892 | 0.351349 | [-0.252993, 0.807962] |
| team_change:True | hierarchical_pl__full | 8 | 1.567445 | 0.121965 | [-0.696428, 0.852223] |
| team_change:True | xgb_ranking__full | 8 | 1.317445 | 0.371965 | [-0.071392, 0.806228] |
| team_change:True | xgb_regression__full | 8 | 1.323937 | 0.365473 | [-0.323989, 1.014961] |
| missing_history:True | hierarchical_pl__full | 10 | 1.443094 | 0.183837 | [-0.123974, 0.565987] |
| missing_history:True | xgb_ranking__full | 10 | 1.443094 | 0.183837 | [-0.306314, 0.603643] |
| missing_history:True | xgb_regression__full | 10 | 1.500885 | 0.126046 | [-0.525723, 0.734002] |
| missing_qualifying:True | hierarchical_pl__full | 1 | 0.932707 | 0.569180 | N/A |
| missing_qualifying:True | xgb_ranking__full | 1 | 0.932707 | 0.569180 | N/A |
| missing_qualifying:True | xgb_regression__full | 1 | 0.932707 | 0.569180 | N/A |
| recent_drift:True | hierarchical_pl__full | 24 | 1.524696 | 0.258479 | [-0.263258, 0.694221] |
| recent_drift:True | xgb_ranking__full | 24 | 1.399696 | 0.383479 | [0.116764, 0.641044] |
| recent_drift:True | xgb_regression__full | 24 | 1.345852 | 0.437323 | [-0.025688, 0.941308] |
| recent_drift:False | hierarchical_pl__full | 46 | 1.517826 | 0.195963 | [-0.118306, 0.470059] |
| recent_drift:False | xgb_ranking__full | 46 | 1.322173 | 0.391615 | [0.183088, 0.561194] |
| recent_drift:False | xgb_regression__full | 46 | 1.308035 | 0.405753 | [0.188401, 0.642050] |

These are whole-field losses on races containing the flagged entrant; they are not driver-specific outcome losses. One rookie can flag every race of a season. Cold-start means identity absent from positive-weight refit rows; unseen driver/team effects are zero with known history retained. Rare-entry means ≤3 positive-weight refit appearances; low-experience means ≤3 prior races. **Actual reserve status is unavailable**; the proxy cannot distinguish a reserve from a rookie or returning driver. Team-change flags use provider entry identities and can include constructor renames, not just physical seat moves. Driver/team tags and low-experience slices overlap.

Missing numeric values use training-only medians and explicit indicators; null qualifying does not remove an entrant/race. The one post-qualifying missingness race and eight team-change races are too small for firm conclusions. Original block IDs survive slicing; one block yields N/A CI. Circuit/season/field-size/driver/team/missingness/weather slices and per-race failure contexts remain in the compressed report. No fit/inference trial failed in the measured runs.

## Compute and reproducibility

| Full model | Trial + refit/calibration time | Largest fold mean inference/race |
| --- | ---: | ---: |
| hierarchical_pl__full | 8.498 s | 0.000532 s |
| xgb_ranking__full | 0.964 s | 0.000623 s |
| xgb_regression__full | 0.788 s | 0.000635 s |

Entire first run: 72.636 s; peak RSS 369.016 MiB (includes all models and reporting). Single-thread CPU on macOS arm64, Python 3.12.14, XGBoost 3.2.0, NumPy 2.2.0, SciPy 1.18.1. Per-fold mean inference includes feature transforms and decoder, excludes loading. No worst-race tail latency, isolated model RSS, serving host or accelerator qualification is claimed.

Two clean committed-source repeats are retained under [runs](runs/experiments/), with matching semantic report/model bundle hashes. All 189 trials and 63 model artifacts per run are retained. [Reproduction command and artifact formats](README.md); [model cards](MODEL_CARDS.md).

Source commit: `e3484a3a19c4706c8f182520cb78c36f628c3c74`; preregistration: `08f502d`. No future-superiority claim follows from these development diagnostics. Offline artifacts do not change serving.

## Fingerprints

- dataset_sha256: `21153f3a012bede74987f713d37e8100b2d556f60ffbcced5ca3a578c0c577a2`
- split_sha256: `0cce74e9da0a6e72e75c982c832fdf441b589641cb29872c762b543e061e89aa`
- protocol_sha256: `e02b9a516d0469b90a1563e4485fd14153e907ddb09c6b8f725426124680327b`
- config_sha256: `6e903cc9fed35497d3359074bd2361ac5d28c6995e1824efc6c9baa86e51b524`
- study_config_sha256: `d8f553ffdde0b1b667e93246bd11ddd9ea8ddab59338a5e3adf7d01d235d61c4`
- code_sha256: `c24fcf2f6f6d0c3f3093129282a49b645c0db12a71f8986f7439f014573f906d`
- dependency_lock_sha256: `3837160a2f8338aec547a9a3a01f868560f6edc118807b356dd71f379abffd3d`
- report_sha256: `e379e4c5300e49d8c6efe54d1df259d650ddd43ab1057f5379fc2056d2b0fa20`
- model_bundle_sha256: `8a18f927411999a1d534d45e218e4b13f5a17a56325d55a78e0ae2a061bb1c39`
