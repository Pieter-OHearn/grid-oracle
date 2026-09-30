# WP07 champion/challenger scorecard

Explored chronological reconstruction, 70 races per horizon. As-of coverage 0/70; as-of/prospective scores **N/A**. No model promoted. Incumbent comparison N/A (artifact unavailable).

Development nominees selected by inner-tune loss before outer scoring: pre_weekend: **xgb_ranking**, post_qualifying: **xgb_regression**.

| Horizon | Candidate | LL | Brier | ECE | MAE | Rho | Winner hit | Top3 | Top10 | Coverage | Paired block improvement CI |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| pre_weekend | baseline:uniform | 2.994267 | 0.949925 | 0.000000 | 6.301840 | -0.035312 | 0.000000 | 0.052381 | 0.458571 | 1.000000 | N/A |
| pre_weekend | baseline:standings | 1.903398 | 0.791955 | 0.021467 | 3.039921 | 0.670863 | 0.428571 | 0.566667 | 0.738571 | 1.000000 | N/A |
| pre_weekend | baseline:recent_form | 1.954942 | 0.809062 | 0.020860 | 3.002393 | 0.687739 | 0.428571 | 0.519048 | 0.748571 | 1.000000 | N/A |
| pre_weekend | xgb_regression__full | 1.839112 | 0.753608 | 0.013296 | 2.924964 | 0.697128 | 0.471429 | 0.557143 | 0.738571 | 1.000000 | -0.215871 to 0.322993 |
| pre_weekend | xgb_regression__no_recency | 2.179683 | 0.788888 | 0.022671 | 3.212382 | 0.649587 | 0.500000 | 0.466667 | 0.735714 | 1.000000 | -0.714236 to 0.127750 |
| pre_weekend | xgb_regression__recent_season_pool | 1.912374 | 0.778082 | 0.012678 | 2.955073 | 0.693095 | 0.442857 | 0.552381 | 0.738571 | 1.000000 | -0.346247 to 0.300905 |
| pre_weekend | xgb_ranking__full | 1.965317 | 0.793457 | 0.020579 | 3.109131 | 0.667879 | 0.428571 | 0.519048 | 0.741429 | 1.000000 | -0.459049 to 0.266496 |
| pre_weekend | xgb_ranking__no_recency | 2.091610 | 0.766415 | 0.023432 | 3.109422 | 0.663842 | 0.500000 | 0.528571 | 0.734286 | 1.000000 | -0.655681 to 0.227322 |
| pre_weekend | xgb_ranking__recent_season_pool | 2.054602 | 0.801506 | 0.024864 | 3.051778 | 0.678313 | 0.414286 | 0.500000 | 0.735714 | 1.000000 | -0.525777 to 0.186155 |
| pre_weekend | hierarchical_pl__full | 1.898753 | 0.764990 | 0.016841 | 2.922362 | 0.698384 | 0.471429 | 0.523810 | 0.748571 | 1.000000 | -0.361606 to 0.342481 |
| pre_weekend | hierarchical_pl__no_recency | 1.991610 | 0.765467 | 0.022555 | 2.956627 | 0.697813 | 0.500000 | 0.519048 | 0.745714 | 1.000000 | -0.490474 to 0.289569 |
| pre_weekend | hierarchical_pl__recent_season_pool | 1.890317 | 0.762063 | 0.014984 | 2.917585 | 0.701502 | 0.471429 | 0.504762 | 0.750000 | 1.000000 | -0.253859 to 0.269709 |
| post_qualifying | baseline:uniform | 2.994267 | 0.949925 | 0.000000 | 6.301840 | -0.035312 | 0.000000 | 0.052381 | 0.458571 | 1.000000 | N/A |
| post_qualifying | baseline:standings | 1.903398 | 0.791955 | 0.021467 | 3.039921 | 0.670863 | 0.428571 | 0.566667 | 0.738571 | 1.000000 | N/A |
| post_qualifying | baseline:recent_form | 1.954942 | 0.809062 | 0.020860 | 3.002393 | 0.687739 | 0.428571 | 0.519048 | 0.748571 | 1.000000 | N/A |
| post_qualifying | baseline:qualifying | 1.737578 | 0.748493 | 0.039199 | 2.495831 | 0.750063 | 0.614286 | 0.666667 | 0.790000 | 1.000000 | N/A |
| post_qualifying | xgb_regression__full | 1.321001 | 0.613513 | 0.010077 | 2.428201 | 0.773083 | 0.600000 | 0.642857 | 0.794286 | 1.000000 | 0.184784 to 0.660135 |
| post_qualifying | xgb_regression__no_recency | 1.385024 | 0.612149 | 0.015814 | 2.396029 | 0.775112 | 0.628571 | 0.647619 | 0.784286 | 1.000000 | 0.098475 to 0.580231 |
| post_qualifying | xgb_regression__recent_season_pool | 1.497595 | 0.665573 | 0.009195 | 2.438154 | 0.772127 | 0.585714 | 0.628571 | 0.801429 | 1.000000 | -0.041212 to 0.524875 |
| post_qualifying | xgb_regression__no_qualifying | 1.839112 | 0.753608 | 0.013296 | 2.924964 | 0.697128 | 0.471429 | 0.557143 | 0.738571 | 1.000000 | -0.422568 to 0.213038 |
| post_qualifying | xgb_ranking__full | 1.348753 | 0.656649 | 0.019902 | 2.457862 | 0.768573 | 0.600000 | 0.661905 | 0.800000 | 1.000000 | 0.222184 to 0.533298 |
| post_qualifying | xgb_ranking__no_recency | 1.342628 | 0.601810 | 0.010801 | 2.454835 | 0.768000 | 0.628571 | 0.657143 | 0.784286 | 1.000000 | 0.096147 to 0.686881 |
| post_qualifying | xgb_ranking__recent_season_pool | 1.633174 | 0.732453 | 0.020084 | 2.461728 | 0.766280 | 0.542857 | 0.623810 | 0.801429 | 1.000000 | -0.122999 to 0.337139 |
| post_qualifying | xgb_ranking__no_qualifying | 1.965317 | 0.793457 | 0.020579 | 3.109131 | 0.667879 | 0.428571 | 0.519048 | 0.741429 | 1.000000 | -0.611668 to 0.120508 |
| post_qualifying | hierarchical_pl__full | 1.520181 | 0.703319 | 0.022003 | 2.345068 | 0.785106 | 0.571429 | 0.647619 | 0.792857 | 1.000000 | -0.051458 to 0.460733 |
| post_qualifying | hierarchical_pl__no_recency | 1.385486 | 0.625533 | 0.006515 | 2.346703 | 0.783419 | 0.571429 | 0.652381 | 0.785714 | 1.000000 | 0.033580 to 0.649734 |
| post_qualifying | hierarchical_pl__recent_season_pool | 1.448753 | 0.689973 | 0.023236 | 2.324511 | 0.786189 | 0.585714 | 0.671429 | 0.794286 | 1.000000 | 0.090671 to 0.477877 |
| post_qualifying | hierarchical_pl__no_qualifying | 1.898753 | 0.764990 | 0.016841 | 2.922362 | 0.698384 | 0.471429 | 0.523810 | 0.748571 | 1.000000 | -0.593222 to 0.251657 |

Positive improvement means comparator minus challenger. Fixed comparators: pre-weekend standings; post-qualifying qualifying. Both race and four-race paired intervals (2,000 draws), loss intervals, all baseline comparisons and ablation-vs-full pairs are in report.json.gz.

Full JSON includes every prediction, cohort/target hash, denominator, reliability bin, fold and predeclared slice. Trials and model artifacts include fitting row hashes, optimizer diagnostics, selected configs, preprocessing and decoder powers.

| Compute scope | Measurement |
| --- | --- |
| Entire run (dataset, fitting, scoring, slices, serialization) | 72.624 s |
| Peak process RSS, includes all retained models | 362.672 MiB |
| Largest measured mean inference per race (model + decoder) | 0.000663 s |
| Attempted tuning fits | 189 |

Local single-thread CPU experiment; timing is per-fold mean, not worst-race latency or deployment qualification. Runtime/costs are separate from semantic results. Prediction artifacts are additive and offline.

Grid/weather/practice/tyre ablations N/A: absent from the frozen WP05 contract. Season pooling tests one regulation era only. Rare-entry slices are proxies, not verified reserve status. Four calibration races give weak calibration evidence. Negative and inconclusive outcomes remain retained.

Promotion guardrails remain frozen: prospective/operational evidence and independent WP09 review are missing. No future-superiority claim follows from this diagnostic table.

## Fingerprints

- code_sha256: `ff8182ea639c311903dba89c2aa57d59b0cd60b09666fd62f026330d0d13b91d`
- dependency_lock_sha256: `3837160a2f8338aec547a9a3a01f868560f6edc118807b356dd71f379abffd3d`
- study_config_sha256: `d8f553ffdde0b1b667e93246bd11ddd9ea8ddab59338a5e3adf7d01d235d61c4`
- study_semantic_sha256: `0d99a0bd5455faafd8184872b4f277dee2a8ec688616becb8b9ce6426e249955`
- dataset_sha256: `21153f3a012bede74987f713d37e8100b2d556f60ffbcced5ca3a578c0c577a2`
- split_sha256: `0cce74e9da0a6e72e75c982c832fdf441b589641cb29872c762b543e061e89aa`
- config_sha256: `6e903cc9fed35497d3359074bd2361ac5d28c6995e1824efc6c9baa86e51b524`
- protocol_sha256: `e02b9a516d0469b90a1563e4485fd14153e907ddb09c6b8f725426124680327b`
- lock_sha256: `fa55bee0b5abe02f3f48bc8f9971a558f69f62dd2e49f5647ca8710c9b9dc8bb`
- report_sha256: `fd1a81cc5bfa2a4b465ed627c1e387bf14e1f2114f10452d5548d104dac02749`
