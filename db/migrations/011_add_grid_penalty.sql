-- TICKET 033 — Grid penalties as a training and prediction feature
-- Add grid_penalty column to qualifying_results to capture post-penalty grid drops

ALTER TABLE qualifying_results
    ADD COLUMN IF NOT EXISTS grid_penalty INTEGER;

COMMENT ON COLUMN qualifying_results.grid_penalty IS
    'Grid position delta applied after qualifying. Positive = places dropped due to a penalty '
    '(e.g. 5 = dropped 5 places). Negative = promoted due to another driver''s penalty '
    '(e.g. -2 = moved up 2 places). '
    'Actual starting position = grid_position + grid_penalty. NULL means no change.';
