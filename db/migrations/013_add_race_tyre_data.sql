-- Migration 013: add race_tyre_data table
-- Stores per-driver lap counts for each tyre compound used in a race session.
-- Used to compute circuit_tyre_degradation_index and
-- constructor_hard_compound_avg_position ML features.

CREATE TABLE race_tyre_data (
    id          SERIAL  PRIMARY KEY,
    race_id     INTEGER NOT NULL REFERENCES races(id),
    driver_id   INTEGER NOT NULL REFERENCES drivers(id),
    compound    TEXT    NOT NULL,  -- 'SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET'
    lap_count   INTEGER NOT NULL,
    UNIQUE (race_id, driver_id, compound)
);

CREATE INDEX idx_race_tyre_data_race   ON race_tyre_data (race_id);
CREATE INDEX idx_race_tyre_data_driver ON race_tyre_data (driver_id);
