# WP07 classical study (preregistered)

Consume WP06 v2 and WP05 immutable inputs. The owner assigned this study on
2026-09-30. Commit this specification/config before any outer scoring. Three
bounded trials per family/variant/fold/horizon; no adaptive search or outer-score
selection. Family champion is chosen using the mean of its three best inner-tune
losses for the **full** variant, separately by horizon. It is a development nominee,
not a production selection. Baseline comparator identities are fixed in config;
no deployed incumbent artifact was supplied, so incumbent comparison is N/A.

All families receive the identical registered numeric features plus verified
entry driver/constructor identities. There are no circuit/time/target columns in
features. Identity vocabularies, medians and scales fit only the training block
(or train+tune refit); unseen identities get zero effects. Missing numeric values
use training medians (all-null columns use zero) plus explicit missing indicators.
No outer labels enter models, transforms, hyperparameters or decoder fitting.
Earlier outer outcomes can appear in later races' frozen lagged features as WP06
permits. Weights and identity effects remain fixed within each outer fold.

## Regression

CPU histogram XGBoost `reg:squarederror` fits contiguous classified rank (smaller
is better). Unclassified labels are masked **inside** the verified whole-field
adapter, never turned into final places. Scores are the negative predicted rank.
L1/L2 penalties, depth, leaf-weight thresholds, learning rate, tree count and
seed are explicit. Every fit is forward in time; no shuffled CV, reverse-time
training, calibration features or final grid. Equal-race training weights normalize
by classified field size. One-hot driver/team identities are shared with the PL
model; they carry no ordinal coding.

## Ranking

XGBoost `rank:pairwise`, one query per race, qids sorted chronologically.
**Higher relevance is better:** relevance = classified_count - contiguous_rank;
the winner gets count-1 and the last classified entrant gets 0. Missing labels
are excluded inside the fit, preserving all entrants at prediction time. Query
weights apply per race, not per driver. Pairwise relevance has no exponential
NDCG-gain interpretation. No early stopping on outer/calibration rows.
See [XGBoost 3.2 learning-to-rank](https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/learning_to_rank.html)
and [query-weight API](https://xgboost.readthedocs.io/en/release_3.2.0/python/python_api.html).

## Hierarchical Plackett–Luce

A non-neural penalized full-ranking likelihood: linear numeric/missing-indicator
features plus additive driver and constructor effects with zero-centered Gaussian
shrinkage (MAP; diagonal quadratic penalty, shared tuned strength). Separate
identity effects partially pool entrants toward the population and share team
information for new drivers. No Bayesian posterior uncertainty is claimed.
Optimize the sequential conditional PL likelihood over **classified entrants**,
equal race weights, with L-BFGS and an analytic gradient. This conditions on
classification and is not a model of DNS/DSQ or retirement. Recency-weighted fits
provide time adaptation across folds; no online outer-outcome skill updates.
An optimizer failure fails the trial and is retained; never silently use an
unconverged artifact. Unknown driver/team effects are zero, with known numeric
history retained. Team effects follow current entry identity after a team change.

## Shared calibrated winner decoder

Raw regression/ranker/PL scores assert an order, not winner probabilities.
All models use the same separate decoder: average occupied zero-based ranks for
score ties; initial PL strength exp(-rank/4), exactly the WP06 v2 ordinal decoder.
After hyperparameters and refit weights are fixed, fit a single bounded power
of those winner probabilities using only the four frozen calibration races.
Minimize equal-race winner log loss over config's five powers through WP06's
verified `fit_calibrator`. Normalize power-transformed strengths by race. This
preserves order and tie equality, has full entrant coverage and finite probabilities.
Report both uncalibrated and calibrated scores/reliability. Four races are very
few: discrete selection can overfit and drift; no calibration guarantee is made.
There are no podium/top-ten probability claims, DNF probabilities or gap confidence.

## Ablations and slices fixed before scoring

`no_recency`: remove short-form means, counts and reliability; disable age weighting.
Season standings, identities and explicit missing flags remain, so this measures
short-form recency increment, not every historical signal.
`recent_season_pool`: retain the verified fitting rows but assign zero weight to
seasons before the newest fitting season. This tests cross-season pooling within
the sole 2022 regulation era; it cannot establish cross-regulation transfer.
`no_qualifying`: post-qualifying only, remove both qualifying features and the
qualifying missing flag; current-session removal is separate from actual grid.
Grid/weather/practice/tyre ablations are N/A: none exists in the frozen dictionary.
Every variant is independently tuned within the same permitted inner block and
calibrated within the same permitted calibration block; no outer-based pruning.

Whole-race slices retain original four-race block IDs: missing history/qualifying,
new identity since refit, <=3 prior driver races, <=3 fitting appearances (rare-entry
proxy, **not verified reserve status**), team changes since the previous entry,
last eight races per evaluation season, season/circuit/field/driver/team/era/weather.
Actual reserve designation is absent; no reserve-specific measured score is invented.
Small/overlapping slices are descriptive and never used for tuning or selection.
Ranking exclusions remain separate from the full winner denominator.

## Evidence and non-use

The entire history is explored, reconstructed from later retrievals and entry lists
from results. As-of coverage 0/70; prospective scores N/A, enrollment pending.
All configurations, trial failures, predictions, fitting row hashes, fitted weights,
preprocessing, calibration, code/dependency/data hashes and compute are retained.
WP06 paired bootstrap and guardrails remain unchanged. Resource timings are local
CPU measurements, not deployment qualification. Existing serving stays unchanged;
WP09 owns independent model selection, WP15 future evidence. Rollback stops
consuming this additive study and preserves attempts and artifacts.
