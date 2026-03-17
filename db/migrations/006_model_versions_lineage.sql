-- TICKET 022 — Record training lineage in model_versions
ALTER TABLE model_versions
    ADD COLUMN train_seasons          INTEGER[],
    ADD COLUMN test_season            INTEGER,
    ADD COLUMN triggered_by_race_id   INTEGER REFERENCES races(id);
