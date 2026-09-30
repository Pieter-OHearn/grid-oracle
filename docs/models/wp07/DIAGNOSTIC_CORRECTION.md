# WP07 review correction: effective fitting exposure

Delegated reviewer `/root/wp07_review` found one P2 issue on PR #101 at
`2044159c68f632e2737ed9aef7f3a9fba1514d7d`. The owner requested the fix.
Correction source: `e3484a3a19c4706c8f182520cb78c36f628c3c74`.

`failure_tags()` counted every refit row even when `recent_season_pool` assigned
older seasons zero weight. The model encoder already excluded those rows.
The diagnostics now receive the selected candidate's actual fitting weights,
validate them, and count identities/appearances only where weight is positive.
Historical entry/team-change and low-experience facts still use the complete
known history; exclusion from training does not erase those facts.

## Concrete result

In the 2024 fold, Ricciardo has **3 positive-weight fitting appearances**, not 25.
He entered 18 evaluation races; 4 already carried another rare-entry flag, so
14 additional races now join the pooled models' rare-entry slice. The count
changes **56 → 70 races** for all six pooled candidates (three families × two
horizons). Across these six candidates, 252 entrant-context annotations and
84 whole-race slice-tag records change. Cold-start identity membership uses
the same corrected scope; no additional cold-start race tags change in this cohort.

The removed false-slice guardrail failures are:

| Candidate | Removed failure |
| --- | --- |
| pre_weekend / hierarchical_pl__recent_season_pool | slice rare_entry:False regressed or missing |
| pre_weekend / xgb_ranking__recent_season_pool | slice rare_entry:False regressed or missing |
| post_qualifying / hierarchical_pl__recent_season_pool | slice rare_entry:False regressed or missing |

`rare_entry:False` now has zero races for pooled candidates, so it cannot trigger
the ≥10-race slice guardrail. Other reasons are unchanged. The six pooled
slices and their paired intervals/guardrail data are regenerated from the full
scheduled denominator. No race, target, driver or forecast is removed.

**Every prediction, trained model artifact, overall metric, trial result and
nominee is unchanged.** All fifteen unpooled candidate result objects are
exactly equal to the original results. The same model-file bundle hash proves
artifact byte equality. Full-model conclusions remain unchanged: pre-weekend
inconclusive; post-qualifying regression improves probability scores but misses
the podium-overlap guardrail. This correction confers no promotion eligibility.

## Corrected evidence (additive)

Two runs measured clean correction source:

- [wp07-4875d84397424aefb6fea4303b0d394d](runs/experiments/wp07-4875d84397424aefb6fea4303b0d394d/run-manifest.json): 72.636 s, peak RSS 369.016 MiB.
- [wp07-225bb78a520d42a89ff0a20df82bf546](runs/experiments/wp07-225bb78a520d42a89ff0a20df82bf546/run-manifest.json): 71.444 s, peak RSS 378.375 MiB.

| Artifact | SHA-256 |
| --- | --- |
| Corrected code | `c24fcf2f6f6d0c3f3093129282a49b645c0db12a71f8986f7439f014573f906d` |
| Corrected semantic report (both runs) | `e379e4c5300e49d8c6efe54d1df259d650ddd43ab1057f5379fc2056d2b0fa20` |
| Model-file bundle (all four runs) | `8a18f927411999a1d534d45e218e4b13f5a17a56325d55a78e0ae2a061bb1c39` |

The original `wp07-298685e2592d4d86a182e1af17d3740e` and
`wp07-f787dfdd3ef9499c83b35ad5d1b3eb2f` directories remain byte-for-byte intact.
Their pooled-exposure diagnostics are superseded; original predictions and
artifacts remain valid. No failed attempt or trial was erased. Repeat hashes
are compared within a measured code revision; differing corrected/historical
report hashes are expected. Current per-horizon reports consume corrected data.

WP06 protocol/config/lock, WP05 dataset, cohort/splits, study config, training,
calibration, seeds and promotion tolerances are unchanged. No new tuning or
outer-based nomination, serving change, database work, deployment or WP09 work.

## Verification

- Eight added regression cases: full/no-recency/pooled Ricciardo exposure,
  zero-weight cold start with intact team/history facts, and invalid weight vectors.
- `make check`: passed.
- `make test`: 28 API, 376 pipeline (31 WP07, 100 benchmark), 3 dashboard tests passed.
- Dashboard build: passed.
- Corrected clean-source repeats: identical code/report/model bundle hashes.
- Compared every original/corrected prediction, global calibrated scorecard,
  unpooled candidate result object and selection; unchanged as stated above.
- Frozen lock and corrected measured-source fingerprints verified.

Independent re-review of the correction remains outstanding. Original reviewer
checks were 21 read-only tests plus all 126 original artifact replays; two
file-writing tests were intentionally excluded during that read-only review.
