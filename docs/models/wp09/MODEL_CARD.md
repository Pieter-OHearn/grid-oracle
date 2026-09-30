# WP09 model selection card

Status: baseline retention recommended separately by horizon; no new production
champion or live forecast. Winner is the primary product target. Accuracy claims
require the unchanged WP06 v2 prospective gate and independent review.

| Horizon | Retained fixed fallback | Calibration | Why |
| --- | --- | --- | --- |
| Pre-weekend | Race-only standings, tied-rank PL scale 4 | Identity (locked) | No eligible challenger; prospective/as-of evidence absent |
| Post-qualifying | Verified qualifying order, tied-rank PL scale 4 | Identity (locked) | No eligible challenger; prospective/as-of evidence absent |

All intended entrants are retained. Missing standings use the field midpoint;
missing qualifying falls back to standings. Tied scores receive equal probability;
driver identity only breaks deterministic-order ties. These identities were fixed
in WP07's preregistered study config, not selected by WP09 outer scores.

Inputs: the immutable WP05 reconstruction, WP06 dataset/splits/v2 config/protocol,
WP07 corrected experiment `wp07-4875d84397424aefb6fea4303b0d394d` (semantic report
`e379e4c5300e49d8c6efe54d1df259d650ddd43ab1057f5379fc2056d2b0fa20`), WP08 clean
experiment `wp08-102c448a77374d9f87bc8d0f434f9605` (semantic report
`2f803356501a3ff58f690107281c13b30029d8e79c29e2fd4ae93bfc4cbd59d6`). Exact
file/source/config/checkpoint fingerprints are in `input-lock.json` and run manifests.
Original runs, failed trials and superseded WP07 exposure diagnostics are preserved.

Comparison scope: all 21 WP07 horizon/variant families, all four WP08 horizon/family
pairs and the seven required horizon/baseline pairs, each on 70 identical outer
races. Classical families are XGBoost regression/ranking and hierarchical PL;
custom families are linear reference and small nonlinear PL. There is no new
ensemble, search or tuning on evaluation results. The best descriptive loss is
not used to switch the predeclared nomination or fallback.

Limitations: only explored 2022–2025 reconstructed history, one regulation era,
unknown input/entry availability, four-race calibration blocks, no deployed
incumbent artifact, no 2027–2028 enrolled prospective cohort, and no operational
shadow races. CUDA is unqualified on this Mac. CPU research timings and backend
parity do not qualify the serving host. Calibration can regress under drift.

Official top-k, points and retirement probabilities are unavailable. Conditional
rank simulation is an explicit PL assumption, not a richer correlated incident,
weather or retirement simulator. Its shared permutation dependence is tested;
no such richer simulator is released by WP09.

Rollback: remove consumers of this additive selection module or explicitly select
a prior champion in the local ledger. No historical artifact, run, forecast or
experiment is deleted. No schema/backfill, deployment or existing service change.
