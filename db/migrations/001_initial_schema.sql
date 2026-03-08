-- TICKET 002 — Database schema and migrations
-- Initial schema for GridOracle

CREATE TABLE IF NOT EXISTS circuits (
    id            SERIAL PRIMARY KEY,
    name          TEXT    NOT NULL UNIQUE,
    country       TEXT    NOT NULL,
    city          TEXT    NOT NULL,
    circuit_type  TEXT    NOT NULL,
    total_laps    INTEGER NOT NULL,
    length_km     NUMERIC(6, 3) NOT NULL
);

CREATE TABLE IF NOT EXISTS races (
    id           SERIAL PRIMARY KEY,
    season       INTEGER NOT NULL,
    round        INTEGER NOT NULL,
    name         TEXT    NOT NULL,
    circuit_id   INTEGER NOT NULL REFERENCES circuits (id),
    date         DATE    NOT NULL,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (season, round)
);

CREATE TABLE IF NOT EXISTS drivers (
    id              SERIAL PRIMARY KEY,
    code            CHAR(3)  NOT NULL UNIQUE,
    full_name       TEXT     NOT NULL,
    nationality     TEXT     NOT NULL,
    date_of_birth   DATE
);

CREATE TABLE IF NOT EXISTS constructors (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    nationality  TEXT NOT NULL,
    color_hex    CHAR(7) NOT NULL
);

CREATE TABLE IF NOT EXISTS driver_contracts (
    id              SERIAL PRIMARY KEY,
    driver_id       INTEGER NOT NULL REFERENCES drivers (id),
    constructor_id  INTEGER NOT NULL REFERENCES constructors (id),
    season          INTEGER NOT NULL,
    UNIQUE (driver_id, season)
);

CREATE TABLE IF NOT EXISTS race_results (
    id               SERIAL PRIMARY KEY,
    race_id          INTEGER NOT NULL REFERENCES races (id),
    driver_id        INTEGER NOT NULL REFERENCES drivers (id),
    constructor_id   INTEGER NOT NULL REFERENCES constructors (id),
    grid_position    INTEGER,
    finish_position  INTEGER,
    points           NUMERIC(5, 2) NOT NULL DEFAULT 0,
    status           TEXT NOT NULL,
    fastest_lap      BOOLEAN NOT NULL DEFAULT FALSE,
    is_wet_race      BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (race_id, driver_id)
);

CREATE TABLE IF NOT EXISTS qualifying_results (
    id              SERIAL PRIMARY KEY,
    race_id         INTEGER NOT NULL REFERENCES races (id),
    driver_id       INTEGER NOT NULL REFERENCES drivers (id),
    constructor_id  INTEGER NOT NULL REFERENCES constructors (id),
    q1_time         INTERVAL,
    q2_time         INTERVAL,
    q3_time         INTERVAL,
    grid_position   INTEGER,
    UNIQUE (race_id, driver_id)
);

CREATE TABLE IF NOT EXISTS weather_snapshots (
    id                SERIAL PRIMARY KEY,
    race_id           INTEGER     NOT NULL REFERENCES races (id),
    captured_at       TIMESTAMPTZ NOT NULL,
    rain_probability  NUMERIC(5, 2),
    temp_celsius      NUMERIC(5, 2),
    wind_speed        NUMERIC(6, 2),
    conditions        TEXT
);

CREATE TABLE IF NOT EXISTS features (
    id            SERIAL PRIMARY KEY,
    race_id       INTEGER     NOT NULL REFERENCES races (id),
    driver_id     INTEGER     NOT NULL REFERENCES drivers (id),
    generated_at  TIMESTAMPTZ NOT NULL,
    feature_data  JSONB       NOT NULL,
    UNIQUE (race_id, driver_id)
);

CREATE TABLE IF NOT EXISTS model_versions (
    id                   SERIAL PRIMARY KEY,
    name                 TEXT        NOT NULL,
    trained_at           TIMESTAMPTZ NOT NULL,
    training_races_count INTEGER     NOT NULL,
    notes                TEXT
);

CREATE TABLE IF NOT EXISTS predictions (
    id                 SERIAL PRIMARY KEY,
    race_id            INTEGER NOT NULL REFERENCES races (id),
    model_version_id   INTEGER NOT NULL REFERENCES model_versions (id),
    driver_id          INTEGER NOT NULL REFERENCES drivers (id),
    constructor_id     INTEGER NOT NULL REFERENCES constructors (id),
    predicted_position INTEGER NOT NULL,
    confidence_score   NUMERIC(5, 4),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (race_id, model_version_id, driver_id)
);

CREATE TABLE IF NOT EXISTS evaluation_metrics (
    id                       SERIAL PRIMARY KEY,
    race_id                  INTEGER NOT NULL REFERENCES races (id),
    model_version_id         INTEGER NOT NULL REFERENCES model_versions (id),
    evaluated_at             TIMESTAMPTZ NOT NULL,
    top3_accuracy            NUMERIC(5, 4),
    exact_position_accuracy  NUMERIC(5, 4),
    mean_position_error      NUMERIC(6, 4),
    UNIQUE (race_id, model_version_id)
);

-- Indexes on commonly queried foreign keys and filter columns
CREATE INDEX IF NOT EXISTS idx_races_season                    ON races (season);
CREATE INDEX IF NOT EXISTS idx_races_circuit_id               ON races (circuit_id);
CREATE INDEX IF NOT EXISTS idx_driver_contracts_season        ON driver_contracts (season);
CREATE INDEX IF NOT EXISTS idx_driver_contracts_driver        ON driver_contracts (driver_id);
CREATE INDEX IF NOT EXISTS idx_race_results_race_id           ON race_results (race_id);
CREATE INDEX IF NOT EXISTS idx_race_results_driver_id         ON race_results (driver_id);
CREATE INDEX IF NOT EXISTS idx_qualifying_results_race_id     ON qualifying_results (race_id);
CREATE INDEX IF NOT EXISTS idx_qualifying_results_driver_id   ON qualifying_results (driver_id);
CREATE INDEX IF NOT EXISTS idx_weather_snapshots_race_id      ON weather_snapshots (race_id);
CREATE INDEX IF NOT EXISTS idx_features_race_id               ON features (race_id);
CREATE INDEX IF NOT EXISTS idx_features_driver_id             ON features (driver_id);
CREATE INDEX IF NOT EXISTS idx_predictions_race_id            ON predictions (race_id);
CREATE INDEX IF NOT EXISTS idx_predictions_driver_id          ON predictions (driver_id);
CREATE INDEX IF NOT EXISTS idx_predictions_model_version_id   ON predictions (model_version_id);
CREATE INDEX IF NOT EXISTS idx_evaluation_metrics_race_id     ON evaluation_metrics (race_id);
