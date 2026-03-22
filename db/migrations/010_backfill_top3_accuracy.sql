-- TICKET 027 — Widen top3_accuracy column and backfill to fixed-denominator formula
--
-- The evaluate.py formula was updated to divide by fixed N (3) rather than the
-- count of actual top-3 finishers. This migration aligns the database column type
-- with the ORM (NUMERIC(6, 4)) and recomputes all existing rows so that stored
-- historical values are consistent with the new formula.
BEGIN;

-- Widen the column to match the ORM definition and the other accuracy columns
ALTER TABLE evaluation_metrics
    ALTER COLUMN top3_accuracy TYPE NUMERIC(6, 4);

-- Recompute all existing rows using the fixed-denominator formula:
-- count of drivers where both predicted_position <= 3 AND finish_position <= 3,
-- divided by the fixed constant 3, matching compute_metrics() in evaluate.py.
UPDATE evaluation_metrics em
SET top3_accuracy = ROUND(
    (
        SELECT COUNT(*)::NUMERIC
        FROM predictions p
        JOIN race_results rr
          ON rr.race_id = p.race_id
         AND rr.driver_id = p.driver_id
        WHERE p.race_id = em.race_id
          AND p.model_version_id = em.model_version_id
          AND rr.finish_position IS NOT NULL
          AND p.predicted_position <= 3
          AND rr.finish_position <= 3
    ) / 3.0,
    4
);

COMMIT;
