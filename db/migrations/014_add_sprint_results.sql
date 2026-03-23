-- Sprint results table for sprint weekend races.
-- Stores each driver's sprint race finish position, status and points.
-- One row per driver per sprint race (race_id, driver_id is unique).

CREATE TABLE sprint_results (
    id            SERIAL PRIMARY KEY,
    race_id       INTEGER      NOT NULL REFERENCES races(id),
    driver_id     INTEGER      NOT NULL REFERENCES drivers(id),
    sprint_position INTEGER,
    status        VARCHAR(50),
    points        NUMERIC(5, 2),
    UNIQUE (race_id, driver_id)
);

CREATE INDEX idx_sprint_results_race_id   ON sprint_results(race_id);
CREATE INDEX idx_sprint_results_driver_id ON sprint_results(driver_id);
