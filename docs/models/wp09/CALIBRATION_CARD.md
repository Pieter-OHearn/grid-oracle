# WP09 calibration and joint-output card

The selected baseline uses WP06's **identity calibration** and fixed scale 4.
Changing that scale after viewing scores would create a new study, so WP09 does
not fit it. Calibration is not evidence of future probability accuracy by itself.

For comparison, every WP07 artifact retains its original mean-tied-rank PL winner
decoder and bounded power from {0.25, 0.5, 1, 2, 4}; WP08 retains its registered
softmax temperature grid. WP09 reloads weights and recomputes held-out calibration
predictions, then uses WP06 `fit_calibrator` to reproduce all 75 choices. Fitted
weights/vocabularies/transforms used only train+tune rows; calibration labels never
enter weights. Calibration race identities, predictions hash, fitting races,
objective, selected power, every trial loss and evaluation deadline are retained.

The frozen blocks are chronological and disjoint. Calibration verifies the supplied
fold against the registered split before checking fitting races or deadlines;
modifying a fold copy cannot expand its permitted training scope. Actual availability remains
unverified in this historical archive, so `asof_eligible` stays false. Supplied
future label timestamps are rejected; absent timestamps do not become verified.
Prospective models must separately freeze calibration and authentic label/input
availability before the forecast cutoff under the existing protocol.

Winner reliability diagrams and exact bin data include both entrant and
contributing-race counts, ten fixed bins and equal-race/1-field-size weights.
Empty bins have null rates. Raw/calibrated proper scores remain visible, including
calibration regressions. Fully classified conditional top-k diagnostic bins have
their own explicit denominator; no censoring labels are invented.

The joint decoder uses winner-stratified permutation draws. It preserves the
winner marginal exactly; all rank and nested conditional top-k marginals come
from the same weighted samples. Marginal Monte Carlo standard-error upper bound
is sqrt(sum(winner_probability²)/(4 × suffix_samples_per_winner)); this is not
confidence in the model. The retained simulation check compares increasing
sample sizes to exact small-field PL probabilities and checks constrained
cross-entry covariance. Seed, algorithm version and sample budget are persisted.

Conditional top-k inherits the winner-calibrated PL strength assumption; it has
**no separately validated official-event calibration**. It is withheld from public
display. Official podium/top-ten, points and retirement remain null until a
separately supported target model exists. This avoids changing winner probabilities
with independently calibrated incompatible top-k classifiers.
