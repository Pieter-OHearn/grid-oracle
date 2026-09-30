# WP07 pre weekend champion/challenger report

Exploratory chronological reconstruction of the frozen WP06 v2 cohort: 70 scheduled races, 2023–2025, 18 original four-race blocks. All entrants retained in winner fields. **As-of coverage 0/70; as-of and prospective metrics N/A. No production model selected.**

Tune-only development nominee: **xgb_ranking__full**. Fixed comparator: **standings**. Incumbent comparison N/A: no deployed artifact supplied. The nominee uses the mean of best inner-fold full-model scores across the study, not a promise of a historical deployment decision or prospective superiority. Outer scores never revise this nomination.

## Observed result and limitations

The inner-tune nominee, XGBoost ranking, regressed against standings by 0.061918
nat; its block improvement CI spans -0.459049 to 0.266496. Regression's 0.064286
nat apparent gain is also inconclusive (-0.215871 to 0.322993). Do not replace the
nominee using the lower outer loss: no full model establishes defensible superiority.
PL differs from standings by just 0.004646 nat. All full models fail numeric
baseline guardrails on this diagnostic cohort.

Short-form recency helped regression and PL in the ablation: removing it raises
loss by 0.340571 / 0.092857 nat, with negative full-minus-ablation block intervals.
Ranker recency and season-pooling comparisons are inconclusive. All-history pooling
is not decisively better for this horizon. Calibration worsened ranker LL from
1.901876 to 1.965317 and PL from 1.873304 to 1.898753: fitting four dominant-winner
races does not guarantee calibration transfer.

The ranker is weakest in the recent-tail slice (24 races, LL 2.329021 versus
1.775558 outside the tail), regressing 0.478375 nat against standings there.
Its ten missing-history races regress 0.418708 nat. Regression also regresses in
the recent tail (0.268778 nat), and all full models struggle in 2024. These are
failure signals for a future study, not permission to retune this study's outer set.
Cold-start/rare-entry flags occur on 56/70 whole races, so favorable scores in
those broad slices cannot establish rookie or reserve performance. Team-change
results cover only eight races and remain inconclusive.

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
| standings | 1.903398 | 0.791955 | 0.021467 | 3.039921 | 0.670863 | 0.428571 | 0.566667 | 0.738571 | 1.000000 | [1.773682, 2.051165] |
| hierarchical_pl__full | 1.898753 | 0.764990 | 0.016841 | 2.922362 | 0.698384 | 0.471429 | 0.523810 | 0.748571 | 1.000000 | [1.487309, 2.341646] |
| xgb_ranking__full | 1.965317 | 0.793457 | 0.020579 | 3.109131 | 0.667879 | 0.428571 | 0.519048 | 0.741429 | 1.000000 | [1.588022, 2.400428] |
| xgb_regression__full | 1.839112 | 0.753608 | 0.013296 | 2.924964 | 0.697128 | 0.471429 | 0.557143 | 0.738571 | 1.000000 | [1.526930, 2.175629] |

Ranking labels exclude unclassified/DNS/DSQ entrants; official top-k sets remain separate. The deterministic order has N/A proper probability scores. Multiclass Brier sums over the entire field; ECE uses WP06 ten fixed bins, entrant weight 1/field size and equal race weight. Low ECE alone does not establish discrimination. Counts and reliability bins are retained in the full JSON.

## Paired uncertainty and diagnostic guardrails

| Full model | Comparator − model LL | Race CI | Four-race block CI | Nominee − model LL | Nominee block CI |
| --- | ---: | --- | --- | ---: | --- |
| hierarchical_pl__full | 0.004646 | [-0.297317, 0.292279] | [-0.361606, 0.342481] | 0.066564 | [-0.198798, 0.340804] |
| xgb_ranking__full | -0.061918 | [-0.349673, 0.210824] | [-0.459049, 0.266496] | 0.000000 | [0.000000, 0.000000] |
| xgb_regression__full | 0.064286 | [-0.197996, 0.324917] | [-0.215871, 0.322993] | 0.126204 | [-0.079495, 0.371887] |

Positive means the challenger has lower loss. WP06 2,000 paired draws, seed 6062026; whole races/blocks only, no driver resampling or silent intersections. These intervals are diagnostic on explored history; many comparisons and slices are not multiplicity-adjusted.

- **hierarchical_pl__full**: insufficient mean winner log-loss improvement; paired block improvement interval inconclusive; top3_overlap_drop failed or missing; slice cold_start:False regressed or missing; slice driver:provider:jolpica:driver:colapinto regressed or missing; slice driver:provider:jolpica:driver:ricciardo regressed or missing; slice rare_entry:False regressed or missing; slice season:2024 regressed or missing; slice team:provider:jolpica:constructor:rb regressed or missing; slice team:provider:jolpica:constructor:sauber regressed or missing.
- **xgb_ranking__full**: insufficient mean winner log-loss improvement; paired block improvement interval inconclusive; top3_overlap_drop failed or missing; slice cold_start:False regressed or missing; slice driver:provider:jolpica:driver:colapinto regressed or missing; slice driver:provider:jolpica:driver:lawson regressed or missing; slice low_experience:False regressed or missing; slice missing_history:True regressed or missing; slice rare_entry:False regressed or missing; slice recent_drift:True regressed or missing; slice season:2024 regressed or missing; slice team:provider:jolpica:constructor:rb regressed or missing; slice team:provider:jolpica:constructor:sauber regressed or missing; slice team_change:False regressed or missing.
- **xgb_regression__full**: paired block improvement interval inconclusive; slice driver:provider:jolpica:driver:colapinto regressed or missing; slice driver:provider:jolpica:driver:lawson regressed or missing; slice recent_drift:True regressed or missing; slice season:2024 regressed or missing; slice team:provider:jolpica:constructor:rb regressed or missing; slice team:provider:jolpica:constructor:sauber regressed or missing.

Every candidate fails prospective review eligibility: future evidence, frozen pre-outcome issuance, incumbent comparison, operational shadow races and resource qualification remain missing. The frozen tolerances and review-gate reasons are retained, without changing benchmark rules.

## Calibration and recent-era drift

| Full model | Raw ordinal LL | Calibrated LL | Powers 2023/2024/2025 | LL 2023 | LL 2024 | LL 2025 |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| hierarchical_pl__full | 1.873304 | 1.898753 | 2.0/4.0/2.0 | 1.091798 | 2.708675 | 1.828539 |
| xgb_ranking__full | 1.901876 | 1.965317 | 2.0/4.0/1.0 | 1.137252 | 2.667008 | 2.022684 |
| xgb_regression__full | 1.847806 | 1.839112 | 2.0/4.0/1.0 | 1.088678 | 2.416383 | 1.949740 |

The shared decoder starts at mean tied rank/temperature 4, then fits one of five powers only on the four calibration races after refit. Higher powers sharpen the distribution. Baselines retain their frozen identity calibration. Thus calibrated uplift includes decoder fitting and cannot be attributed solely to architecture. Four races offer weak protection against drift; raw/calibrated reliability and proper scores are both available. The study contains one regulation era.

## Ablations (independent inner tuning; same outer denominator)

| Variant | LL | Full − variant LL | Paired block CI |
| --- | ---: | ---: | --- |
| hierarchical_pl__no_recency | 1.991610 | -0.092857 | [-0.178571, -0.014286] |
| hierarchical_pl__recent_season_pool | 1.890317 | 0.008436 | [-0.178455, 0.220798] |
| xgb_ranking__no_recency | 2.091610 | -0.126293 | [-0.397914, 0.131535] |
| xgb_ranking__recent_season_pool | 2.054602 | -0.089286 | [-0.297815, 0.159747] |
| xgb_regression__no_recency | 2.179683 | -0.340571 | [-0.742055, -0.031688] |
| xgb_regression__recent_season_pool | 1.912374 | -0.073261 | [-0.228405, 0.064208] |

`no_recency` removes short-form means/counts/reliability and disables age weighting, while preserving season standings, identities and missing flags. `recent_season_pool` gives older fitting seasons zero weight: this is a season-pooling test within one regulation era. `no_qualifying` removes current qualifying and its missing flag in the post-qualifying horizon only. Grid, weather, practice and tyre ablations are **N/A** because no valid registered data exists. No legacy proxies or final-grid values were imported.

## Cold starts, reserves, team changes and missing data

| Slice | Full model | Races | Winner LL | Comparator − model | Block CI |
| --- | --- | ---: | ---: | ---: | --- |
| cold_start:True | hierarchical_pl__full | 56 | 1.651629 | 0.178730 | [-0.127403, 0.446529] |
| cold_start:True | xgb_ranking__full | 56 | 1.877691 | -0.047333 | [-0.508293, 0.304848] |
| cold_start:True | xgb_regression__full | 56 | 1.755878 | 0.074480 | [-0.268854, 0.365803] |
| rare_entry:True | hierarchical_pl__full | 56 | 1.651629 | 0.178730 | [-0.127403, 0.446529] |
| rare_entry:True | xgb_ranking__full | 56 | 1.877691 | -0.047333 | [-0.508293, 0.304848] |
| rare_entry:True | xgb_regression__full | 56 | 1.755878 | 0.074480 | [-0.268854, 0.365803] |
| low_experience:True | hierarchical_pl__full | 19 | 1.810695 | 0.199667 | [-0.234623, 0.563565] |
| low_experience:True | xgb_ranking__full | 19 | 1.970005 | 0.040356 | [-0.735387, 0.608746] |
| low_experience:True | xgb_regression__full | 19 | 1.745046 | 0.265315 | [-0.298970, 0.708616] |
| team_change:True | hierarchical_pl__full | 8 | 1.942445 | 0.384215 | [-0.335923, 1.320469] |
| team_change:True | xgb_ranking__full | 8 | 1.593404 | 0.733256 | [0.114580, 1.665260] |
| team_change:True | xgb_regression__full | 8 | 1.559674 | 0.766985 | [0.119688, 1.705970] |
| missing_history:True | hierarchical_pl__full | 10 | 1.993094 | 0.127059 | [-0.292612, 0.548202] |
| missing_history:True | xgb_ranking__full | 10 | 2.538861 | -0.418708 | [-2.280650, 0.801338] |
| missing_history:True | xgb_regression__full | 10 | 2.088137 | 0.032016 | [-1.127474, 0.892072] |
| missing_qualifying:True | hierarchical_pl__full | 70 | 1.898753 | 0.004646 | [-0.361606, 0.342481] |
| missing_qualifying:True | xgb_ranking__full | 70 | 1.965317 | -0.061918 | [-0.459049, 0.266496] |
| missing_qualifying:True | xgb_regression__full | 70 | 1.839112 | 0.064286 | [-0.215871, 0.322993] |
| recent_drift:True | hierarchical_pl__full | 24 | 1.795530 | 0.055116 | [-0.438595, 0.553729] |
| recent_drift:True | xgb_ranking__full | 24 | 2.329021 | -0.478375 | [-1.251942, 0.219822] |
| recent_drift:True | xgb_regression__full | 24 | 2.119423 | -0.268778 | [-0.815954, 0.255297] |
| recent_drift:False | hierarchical_pl__full | 46 | 1.952608 | -0.021686 | [-0.554353, 0.414872] |
| recent_drift:False | xgb_ranking__full | 46 | 1.775558 | 0.155364 | [-0.154619, 0.461082] |
| recent_drift:False | xgb_regression__full | 46 | 1.692863 | 0.238059 | [0.016217, 0.459707] |

These are whole-field losses on races containing the flagged entrant; they are not driver-specific outcome losses. One rookie can flag every race of a season. Cold-start means identity absent from positive-weight refit rows; unseen driver/team effects are zero with known history retained. Rare-entry means ≤3 positive-weight refit appearances; low-experience means ≤3 prior races. **Actual reserve status is unavailable**; the proxy cannot distinguish a reserve from a rookie or returning driver. Team-change flags use provider entry identities and can include constructor renames, not just physical seat moves. Driver/team tags and low-experience slices overlap.

Missing numeric values use training-only medians and explicit indicators; null qualifying does not remove an entrant/race. The one post-qualifying missingness race and eight team-change races are too small for firm conclusions. Original block IDs survive slicing; one block yields N/A CI. Circuit/season/field-size/driver/team/missingness/weather slices and per-race failure contexts remain in the compressed report. No fit/inference trial failed in the measured runs.

## Compute and reproducibility

| Full model | Trial + refit/calibration time | Largest fold mean inference/race |
| --- | ---: | ---: |
| hierarchical_pl__full | 8.386 s | 0.000480 s |
| xgb_ranking__full | 0.972 s | 0.000608 s |
| xgb_regression__full | 0.958 s | 0.000615 s |

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
