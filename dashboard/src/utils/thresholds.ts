// Confidence score thresholds (0–100) for labelling prediction confidence.
// Based on model backtesting: scores above 70 are reliably accurate.
export const CONFIDENCE_HIGH = 70;
export const CONFIDENCE_STRONG = 55;
export const CONFIDENCE_MODERATE = 40;
export const CONFIDENCE_LOW = 25;

// Mean Position Error (MPE) reference lines for the ErrorLineChart.
// "Good" reflects a model performing well (≤2 positions off on average).
// "Poor" reflects a model that needs attention (≥4 positions off on average).
// Current model MAE is ~3.48, which falls between these thresholds.
export const MPE_GOOD_THRESHOLD = 2.0;
export const MPE_POOR_THRESHOLD = 4.0;

// Exact Hit Rate thresholds (%) for colour-coding bars in ExactHitBarChart.
// ≥25% exact hits is strong; ≥15% is acceptable; below that is poor.
export const EXACT_HIT_STRONG = 25;
export const EXACT_HIT_ACCEPTABLE = 15;
