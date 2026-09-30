# WP09 selection report

Retain **standings** pre-weekend and **qualifying** post-qualifying. No challenger is promoted.
No deployed incumbent artifact was supplied; existing serving is unchanged. These are fixed fallback
recommendations, not a claim of prospective baseline qualification or a publication instruction.

All scores below are exploratory chronological reconstruction of 70 races per horizon.
As-of eligibility: **0/70**. Prospective metrics: **N/A**, enrollment pending. Shadow races: **0**.
Frozen WP06 v2 metrics, cohorts, tolerances and seeds are unchanged. All 75 retained selected
model artifacts and calibration choices were replayed before comparison. Full JSON includes every
prediction, baseline/contender paired race/block interval, raw/calibrated score, slice and failure.

| Horizon | Model | Winner LL | Raw LL | Brier | ECE | Rank MAE | Rho | Hit | Top3 | Top10 | Gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| pre_weekend | hierarchical_pl__full | 1.898753 | 1.873304 | 0.764990 | 0.016841 | 2.922362 | 0.698384 | 0.471429 | 0.523810 | 0.748571 | retain baseline |
| pre_weekend | hierarchical_pl__no_recency | 1.991610 | 1.905447 | 0.765467 | 0.022555 | 2.956627 | 0.697813 | 0.500000 | 0.519048 | 0.745714 | retain baseline |
| pre_weekend | hierarchical_pl__recent_season_pool | 1.890317 | 1.887590 | 0.762063 | 0.014984 | 2.917585 | 0.701502 | 0.471429 | 0.504762 | 0.750000 | retain baseline |
| pre_weekend | xgb_ranking__full | 1.965317 | 1.901876 | 0.793457 | 0.020579 | 3.109131 | 0.667879 | 0.428571 | 0.519048 | 0.741429 | retain baseline |
| pre_weekend | xgb_ranking__no_recency | 2.091610 | 1.930447 | 0.766415 | 0.023432 | 3.109422 | 0.663842 | 0.500000 | 0.528571 | 0.734286 | retain baseline |
| pre_weekend | xgb_ranking__recent_season_pool | 2.054602 | 1.959019 | 0.801506 | 0.024864 | 3.051778 | 0.678313 | 0.414286 | 0.500000 | 0.735714 | retain baseline |
| pre_weekend | xgb_regression__full | 1.839112 | 1.847806 | 0.753608 | 0.013296 | 2.924964 | 0.697128 | 0.471429 | 0.557143 | 0.738571 | retain baseline |
| pre_weekend | xgb_regression__no_recency | 2.179683 | 2.007884 | 0.788888 | 0.022671 | 3.212382 | 0.649587 | 0.500000 | 0.466667 | 0.735714 | retain baseline |
| pre_weekend | xgb_regression__recent_season_pool | 1.912374 | 1.867437 | 0.778082 | 0.012678 | 2.955073 | 0.693095 | 0.442857 | 0.552381 | 0.738571 | retain baseline |
| pre_weekend | wp08_reference | 2.100011 | 2.124244 | 0.768984 | 0.015860 | 3.281217 | 0.625541 | 0.471429 | 0.504762 | 0.714286 | retain baseline |
| pre_weekend | wp08_nonlinear | 1.710246 | 1.835114 | 0.741297 | 0.016737 | 3.096116 | 0.667436 | 0.485714 | 0.547619 | 0.732857 | retain baseline |
| pre_weekend | baseline:uniform | 2.994267 | 2.994267 | 0.949925 | 0.000000 | 6.301840 | -0.035312 | 0.000000 | 0.052381 | 0.458571 | retain baseline |
| pre_weekend | baseline:standings | 1.903398 | 1.903398 | 0.791955 | 0.021467 | 3.039921 | 0.670863 | 0.428571 | 0.566667 | 0.738571 | retain baseline |
| pre_weekend | baseline:recent_form | 1.954942 | 1.954942 | 0.809062 | 0.020860 | 3.002393 | 0.687739 | 0.428571 | 0.519048 | 0.748571 | retain baseline |
| post_qualifying | hierarchical_pl__full | 1.520181 | 1.730447 | 0.703319 | 0.022003 | 2.345068 | 0.785106 | 0.571429 | 0.647619 | 0.792857 | retain baseline |
| post_qualifying | hierarchical_pl__no_qualifying | 1.898753 | 1.873304 | 0.764990 | 0.016841 | 2.922362 | 0.698384 | 0.471429 | 0.523810 | 0.748571 | retain baseline |
| post_qualifying | hierarchical_pl__no_recency | 1.385486 | 1.726876 | 0.625533 | 0.006515 | 2.346703 | 0.783419 | 0.571429 | 0.652381 | 0.785714 | retain baseline |
| post_qualifying | hierarchical_pl__recent_season_pool | 1.448753 | 1.709019 | 0.689973 | 0.023236 | 2.324511 | 0.786189 | 0.585714 | 0.671429 | 0.794286 | retain baseline |
| post_qualifying | xgb_ranking__full | 1.348753 | 1.687590 | 0.656649 | 0.019902 | 2.457862 | 0.768573 | 0.600000 | 0.661905 | 0.800000 | retain baseline |
| post_qualifying | xgb_ranking__no_qualifying | 1.965317 | 1.901876 | 0.793457 | 0.020579 | 3.109131 | 0.667879 | 0.428571 | 0.519048 | 0.741429 | retain baseline |
| post_qualifying | xgb_ranking__no_recency | 1.342628 | 1.705447 | 0.601810 | 0.010801 | 2.454835 | 0.768000 | 0.628571 | 0.657143 | 0.784286 | retain baseline |
| post_qualifying | xgb_ranking__recent_season_pool | 1.633174 | 1.744733 | 0.732453 | 0.020084 | 2.461728 | 0.766280 | 0.542857 | 0.623810 | 0.801429 | retain baseline |
| post_qualifying | xgb_regression__full | 1.321001 | 1.712555 | 0.613513 | 0.010077 | 2.428201 | 0.773083 | 0.600000 | 0.642857 | 0.794286 | retain baseline |
| post_qualifying | xgb_regression__no_qualifying | 1.839112 | 1.847806 | 0.753608 | 0.013296 | 2.924964 | 0.697128 | 0.471429 | 0.557143 | 0.738571 | retain baseline |
| post_qualifying | xgb_regression__no_recency | 1.385024 | 1.717790 | 0.612149 | 0.015814 | 2.396029 | 0.775112 | 0.628571 | 0.647619 | 0.784286 | retain baseline |
| post_qualifying | xgb_regression__recent_season_pool | 1.497595 | 1.733829 | 0.665573 | 0.009195 | 2.438154 | 0.772127 | 0.585714 | 0.628571 | 0.801429 | retain baseline |
| post_qualifying | wp08_reference | 1.866059 | 1.916785 | 0.707809 | 0.013938 | 2.869927 | 0.700936 | 0.471429 | 0.552381 | 0.754286 | retain baseline |
| post_qualifying | wp08_nonlinear | 1.254299 | 1.364893 | 0.593430 | 0.009227 | 2.551269 | 0.750959 | 0.557143 | 0.647619 | 0.784286 | retain baseline |
| post_qualifying | baseline:uniform | 2.994267 | 2.994267 | 0.949925 | 0.000000 | 6.301840 | -0.035312 | 0.000000 | 0.052381 | 0.458571 | retain baseline |
| post_qualifying | baseline:standings | 1.903398 | 1.903398 | 0.791955 | 0.021467 | 3.039921 | 0.670863 | 0.428571 | 0.566667 | 0.738571 | retain baseline |
| post_qualifying | baseline:recent_form | 1.954942 | 1.954942 | 0.809062 | 0.020860 | 3.002393 | 0.687739 | 0.428571 | 0.519048 | 0.748571 | retain baseline |
| post_qualifying | baseline:qualifying | 1.737578 | 1.737578 | 0.748493 | 0.039199 | 2.495831 | 0.750063 | 0.614286 | 0.666667 | 0.790000 | retain baseline |

## Decisions and failures

### pre_weekend

Fixed fallback: `baseline:standings`. WP07 tune nominee remains `xgb_ranking`.

- **hierarchical_pl__full**: baseline minus candidate LL 0.004646, block CI [-0.36160618477965994, 0.34248080567554956]. Diagnostic guardrails: insufficient mean winner log-loss improvement; paired block improvement interval inconclusive; top3_overlap_drop failed or missing; slice cold_start:False regressed or missing; slice driver:provider:jolpica:driver:colapinto regressed or missing; slice driver:provider:jolpica:driver:ricciardo regressed or missing; slice rare_entry:False regressed or missing; slice season:2024 regressed or missing; slice team:provider:jolpica:constructor:rb regressed or missing; slice team:provider:jolpica:constructor:sauber regressed or missing.
- **xgb_ranking__full**: baseline minus candidate LL -0.061918, block CI [-0.45904851296723403, 0.2664960751273095]. Diagnostic guardrails: insufficient mean winner log-loss improvement; paired block improvement interval inconclusive; top3_overlap_drop failed or missing; slice cold_start:False regressed or missing; slice driver:provider:jolpica:driver:colapinto regressed or missing; slice driver:provider:jolpica:driver:lawson regressed or missing; slice low_experience:False regressed or missing; slice missing_history:True regressed or missing; slice rare_entry:False regressed or missing; slice recent_drift:True regressed or missing; slice season:2024 regressed or missing; slice team:provider:jolpica:constructor:rb regressed or missing; slice team:provider:jolpica:constructor:sauber regressed or missing; slice team_change:False regressed or missing.
- **xgb_regression__full**: baseline minus candidate LL 0.064286, block CI [-0.21587065986229406, 0.3229927549080816]. Diagnostic guardrails: paired block improvement interval inconclusive; slice driver:provider:jolpica:driver:colapinto regressed or missing; slice driver:provider:jolpica:driver:lawson regressed or missing; slice recent_drift:True regressed or missing; slice season:2024 regressed or missing; slice team:provider:jolpica:constructor:rb regressed or missing; slice team:provider:jolpica:constructor:sauber regressed or missing.
- **wp08_reference**: baseline minus candidate LL -0.196612, block CI [-0.6430805377854056, 0.22131947463108537]. Diagnostic guardrails: insufficient mean winner log-loss improvement; paired block improvement interval inconclusive; rank_mae_regression failed or missing; rank_correlation_drop failed or missing; top3_overlap_drop failed or missing; top10_overlap_drop failed or missing; slice driver:provider:jolpica:driver:albon regressed or missing; slice driver:provider:jolpica:driver:alonso regressed or missing; slice driver:provider:jolpica:driver:bearman regressed or missing; slice driver:provider:jolpica:driver:bottas regressed or missing; slice driver:provider:jolpica:driver:colapinto regressed or missing; slice driver:provider:jolpica:driver:de_vries regressed or missing; slice driver:provider:jolpica:driver:gasly regressed or missing; slice driver:provider:jolpica:driver:hamilton regressed or missing; slice driver:provider:jolpica:driver:hulkenberg regressed or missing; slice driver:provider:jolpica:driver:kevin_magnussen regressed or missing; slice driver:provider:jolpica:driver:lawson regressed or missing; slice driver:provider:jolpica:driver:leclerc regressed or missing; slice driver:provider:jolpica:driver:max_verstappen regressed or missing; slice driver:provider:jolpica:driver:norris regressed or missing; slice driver:provider:jolpica:driver:ocon regressed or missing; slice driver:provider:jolpica:driver:perez regressed or missing; slice driver:provider:jolpica:driver:piastri regressed or missing; slice driver:provider:jolpica:driver:ricciardo regressed or missing; slice driver:provider:jolpica:driver:russell regressed or missing; slice driver:provider:jolpica:driver:sainz regressed or missing; slice driver:provider:jolpica:driver:stroll regressed or missing; slice driver:provider:jolpica:driver:tsunoda regressed or missing; slice driver:provider:jolpica:driver:zhou regressed or missing; slice era:2022-2025_regulation_cohort regressed or missing; slice field_size:20 regressed or missing; slice missing_history:True regressed or missing; slice missing_qualifying:True regressed or missing; slice season:2024 regressed or missing; slice team:provider:jolpica:constructor:alpine regressed or missing; slice team:provider:jolpica:constructor:aston_martin regressed or missing; slice team:provider:jolpica:constructor:ferrari regressed or missing; slice team:provider:jolpica:constructor:haas regressed or missing; slice team:provider:jolpica:constructor:mclaren regressed or missing; slice team:provider:jolpica:constructor:mercedes regressed or missing; slice team:provider:jolpica:constructor:rb regressed or missing; slice team:provider:jolpica:constructor:red_bull regressed or missing; slice team:provider:jolpica:constructor:sauber regressed or missing; slice team:provider:jolpica:constructor:williams regressed or missing; slice weather:unavailable regressed or missing.
- **wp08_nonlinear**: baseline minus candidate LL 0.193153, block CI [-0.006202936066255954, 0.3833339613346865]. Diagnostic guardrails: paired block improvement interval inconclusive.

Every promotion gate fails: prospective and pre-outcome locking unverified; 0 races/blocks/shadows;
no incumbent comparison or serving resource qualification; unresolved availability evidence. No
candidate is selected by its best observed outer loss, and no ablation replaces the tune nominee.

### post_qualifying

Fixed fallback: `baseline:qualifying`. WP07 tune nominee remains `xgb_regression`.

- **hierarchical_pl__full**: baseline minus candidate LL 0.217397, block CI [-0.05145846878564843, 0.46073312263256555]. Diagnostic guardrails: paired block improvement interval inconclusive; winner_hit_drop failed or missing; slice cold_start:False regressed or missing; slice rare_entry:False regressed or missing; slice season:2024 regressed or missing.
- **xgb_ranking__full**: baseline minus candidate LL 0.388826, block CI [0.22218362513671608, 0.5332982122480002]. Diagnostic guardrails: pass on explored data only.
- **xgb_regression__full**: baseline minus candidate LL 0.416577, block CI [0.18478404829523615, 0.6601351798183711]. Diagnostic guardrails: top3_overlap_drop failed or missing.
- **wp08_reference**: baseline minus candidate LL -0.128481, block CI [-0.5911200998304559, 0.3237277894525336]. Diagnostic guardrails: insufficient mean winner log-loss improvement; paired block improvement interval inconclusive; rank_mae_regression failed or missing; rank_correlation_drop failed or missing; top3_overlap_drop failed or missing; top10_overlap_drop failed or missing; winner_hit_drop failed or missing; slice driver:provider:jolpica:driver:albon regressed or missing; slice driver:provider:jolpica:driver:alonso regressed or missing; slice driver:provider:jolpica:driver:bottas regressed or missing; slice driver:provider:jolpica:driver:colapinto regressed or missing; slice driver:provider:jolpica:driver:de_vries regressed or missing; slice driver:provider:jolpica:driver:gasly regressed or missing; slice driver:provider:jolpica:driver:hamilton regressed or missing; slice driver:provider:jolpica:driver:hulkenberg regressed or missing; slice driver:provider:jolpica:driver:kevin_magnussen regressed or missing; slice driver:provider:jolpica:driver:leclerc regressed or missing; slice driver:provider:jolpica:driver:max_verstappen regressed or missing; slice driver:provider:jolpica:driver:norris regressed or missing; slice driver:provider:jolpica:driver:ocon regressed or missing; slice driver:provider:jolpica:driver:perez regressed or missing; slice driver:provider:jolpica:driver:piastri regressed or missing; slice driver:provider:jolpica:driver:ricciardo regressed or missing; slice driver:provider:jolpica:driver:russell regressed or missing; slice driver:provider:jolpica:driver:sainz regressed or missing; slice driver:provider:jolpica:driver:stroll regressed or missing; slice driver:provider:jolpica:driver:tsunoda regressed or missing; slice driver:provider:jolpica:driver:zhou regressed or missing; slice era:2022-2025_regulation_cohort regressed or missing; slice missing_history:True regressed or missing; slice missing_qualifying:False regressed or missing; slice season:2024 regressed or missing; slice team:provider:jolpica:constructor:alpine regressed or missing; slice team:provider:jolpica:constructor:aston_martin regressed or missing; slice team:provider:jolpica:constructor:ferrari regressed or missing; slice team:provider:jolpica:constructor:haas regressed or missing; slice team:provider:jolpica:constructor:mclaren regressed or missing; slice team:provider:jolpica:constructor:mercedes regressed or missing; slice team:provider:jolpica:constructor:rb regressed or missing; slice team:provider:jolpica:constructor:red_bull regressed or missing; slice team:provider:jolpica:constructor:sauber regressed or missing; slice team:provider:jolpica:constructor:williams regressed or missing; slice weather:unavailable regressed or missing.
- **wp08_nonlinear**: baseline minus candidate LL 0.483279, block CI [0.20647770981576116, 0.7448744056358383]. Diagnostic guardrails: winner_hit_drop failed or missing.

Every promotion gate fails: prospective and pre-outcome locking unverified; 0 races/blocks/shadows;
no incumbent comparison or serving resource qualification; unresolved availability evidence. No
candidate is selected by its best observed outer loss, and no ablation replaces the tune nominee.

## Calibration and output limits

Winner powers/temperatures are replayed exclusively on the four prior calibration races after fixed
train+tune refits. They are out-of-sample relative to weights, but historical availability is unverified.
The baseline keeps locked identity calibration. No new search, ensemble or outer-label calibration occurs.
Winner-stratified PL suffix simulation preserves the winner marginal exactly and produces one coherent
joint distribution. Conditional rank/top-k marginals are nested and sum to the fixed field's slot counts.
They are not official podium/top-ten, points or retirement estimates; those outputs remain null.
Conditional reliability uses fully classified fields only, with excluded races explicit. No such
conditional output is approved for public display. Winner diagrams include all bin entry/race counts.
Simulation standard errors describe Monte Carlo error, not uncertainty in the fitted model.

## Promotion and rollback

The local ledger requires explicit registration, challenger state, independent named review of
a gate-passing artifact bound to the current incumbent, then a separate manual promotion action.
Rollback points to a previously selected champion for the same horizon; it never edits old runs.
No production pointer or database was changed in this experiment. The report records retention only.

WP06's prospective 2027–2028 window and >=40 races/10 blocks/6 shadows remain outstanding.
The current small calibration blocks, explored history, unknown source timestamps, missing incumbent
and absent censoring model limit all interpretations. CPU results do not qualify a deployment host.
