ALTER TABLE evaluation_metrics
    ADD COLUMN IF NOT EXISTS top5_accuracy NUMERIC(6, 4),
    ADD COLUMN IF NOT EXISTS top10_accuracy NUMERIC(6, 4);
