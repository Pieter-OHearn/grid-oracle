-- Migration 012: add session_times table
-- Stores per-driver best sector times (from qualifying) and best lap times
-- (from practice sessions) for use as pre-weekend ML features.

CREATE TABLE session_times (
    id           SERIAL  PRIMARY KEY,
    race_id      INTEGER NOT NULL REFERENCES races(id),
    driver_id    INTEGER NOT NULL REFERENCES drivers(id),
    session_type TEXT    NOT NULL,  -- 'Q' (qualifying) or 'FP2' (second practice)
    best_lap_ms  INTEGER,           -- best full lap time in milliseconds
    sector1_ms   INTEGER,           -- best sector 1 time in milliseconds
    sector2_ms   INTEGER,           -- best sector 2 time in milliseconds
    sector3_ms   INTEGER,           -- best sector 3 time in milliseconds
    UNIQUE (race_id, driver_id, session_type)
);

CREATE INDEX idx_session_times_race_driver   ON session_times (race_id, driver_id);
CREATE INDEX idx_session_times_driver_session ON session_times (driver_id, session_type);
