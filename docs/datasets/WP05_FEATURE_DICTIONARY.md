# WP05 feature dictionary

The executable registry is `pipeline.dataset.historical.FeatureRegistry`. Its
horizon gate removes forbidden columns from pre-weekend Parquet entirely; it
does not merely fill qualifying values with nulls.

| Feature | Tier | Horizon | Definition / provenance |
| --- | --- | --- | --- |
| `driver_finish_mean_last_3` | recency | both | Mean classified finish in the driver's three earlier Grands Prix. |
| `constructor_finish_mean_last_3` | recency | both | Mean of constructor per-race means over three earlier Grands Prix; two cars do not count as two races. |
| `driver_recency_races` | recency | both | Number of prior driver Grand Prix result records. |
| `constructor_recency_races` | recency | both | Number of prior constructor Grand Prix appearances. |
| `driver_reliability_rate_last_3` | reliability | both | Fraction of prior three results with canonical status `finished` or `lapped`. |
| `driver_championship_position_race_only` | recency | both | Prior race-results-only standing. Sprint points are unavailable and not inferred. |
| `constructor_championship_position_race_only` | recency | both | Prior race-results-only constructor standing. |
| `qualifying_position` | normalized pace | post-qualifying only | Current Grand Prix qualifying classification, not final grid. |
| `qualifying_normalized_position` | normalized pace | post-qualifying only | Qualifying position / reconciled qualifying field size. |
| `missing__history` | missingness | both | No prior classified driver result feature exists. |
| `missing__qualifying` | missingness | both | Qualifying unavailable. It is always true in pre-weekend output because qualifying columns are forbidden there. |

The contract intentionally does not expose final-grid, practice, sprint,
weather, compound, degradation, FP2 or sector-time proxies. Any future
addition requires a provenance-compatible availability classification and an
ablation; it cannot mutate this version's dictionary or manifest.
