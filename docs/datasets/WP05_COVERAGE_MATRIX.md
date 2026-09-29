# WP05 coverage matrix

Source: immutable manifest `6ff6b63b470900cb1d55513d91e9362851948d04133b8cd2b216bb7dccf671d2`.
Every partition has source quality `archived_retrieval_known_asof_unknown` and
is excluded from as-of evaluation until authentic availability evidence exists.

| Season | Races | Result entries | Qualifying entries | Pre-weekend rows | Post-qualifying rows | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2022 | 22 | 440 | 440 | 440 | 440 | Baseline coverage complete at archive level. |
| 2023 | 22 | 440 | 440 | 440 | 440 | Baseline coverage complete at archive level. |
| 2024 | 24 | 479 | 479 | 479 | 479 | Baseline coverage complete at archive level. |
| 2025 | 24 | 479 | 479 | 479 | 479 | One qualifying position is null; retained and flagged. |
| Total | 92 | 1,838 | 1,838 | 1,838 | 1,838 | 3,676 horizon-specific feature rows. |

| Audit measure | Value |
| --- | --- |
| Result sessions / qualifying sessions | 92 / 92 |
| Exact duplicate reconciled rows | 0 |
| Identity conflicts | 0 |
| Missing driver form / reliability values | 76 / 62 |
| Missing constructor last-three values | 48 |
| Missing current qualifying fields in combined horizon report | 1 post-qualifying row; all 1,838 pre-weekend rows are structurally excluded |
| Exclusions | As-of evaluation, sprint points, weather, degradation/compound proxies |

The report inside the manifest also keeps the raw page-observation count per
race/session so a resumed backfill can audit paginated source coverage.
