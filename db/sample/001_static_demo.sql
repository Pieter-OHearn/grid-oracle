-- GridOracle static sample data, version 1.
--
-- Provenance: hand-authored local development fixture. It is intentionally
-- small, fictional, and must not be used for model evaluation or publication.
-- It is loaded only by db/init/02_load_sample_data.sh when
-- GRIDORACLE_SAMPLE_DATA=1, into the dedicated sample volume declared in
-- docker-compose.yml. No provider, scheduler, or bootstrap command reads it.

INSERT INTO circuits (id, name, country, city, circuit_type, total_laps, length_km)
VALUES (1, 'GridOracle Test Circuit', 'Exampleland', 'Sample City', 'permanent', 12, 4.200)
ON CONFLICT (id) DO NOTHING;

INSERT INTO constructors (id, name, nationality, color_hex)
VALUES (1, 'Sample Racing', 'Exampleland', '#3671C6')
ON CONFLICT (id) DO NOTHING;

INSERT INTO drivers (id, code, full_name, nationality, number)
VALUES
    (1, 'ONE', 'Avery Example', 'Exampleland', 1),
    (2, 'TWO', 'Blake Example', 'Exampleland', 2)
ON CONFLICT (id) DO NOTHING;

INSERT INTO races (id, season, round, name, circuit_id, date, is_completed)
VALUES (1, 2024, 1, 'Sample Grand Prix', 1, '2024-01-01', TRUE)
ON CONFLICT (id) DO NOTHING;

INSERT INTO driver_contracts (driver_id, constructor_id, season, start_round)
VALUES (1, 1, 2024, 1), (2, 1, 2024, 1)
ON CONFLICT (driver_id, season, start_round) DO NOTHING;

INSERT INTO model_versions (id, name, trained_at, training_races_count, notes)
VALUES (1, 'static-sample-v1', '2024-01-01T00:00:00Z', 0, 'Static local sample; not a trained model.')
ON CONFLICT (id) DO NOTHING;

INSERT INTO predictions (race_id, model_version_id, driver_id, constructor_id, predicted_position, confidence_score, created_at)
VALUES
    (1, 1, 1, 1, 1, 0.5000, '2024-01-01T00:00:00Z'),
    (1, 1, 2, 1, 2, 0.5000, '2024-01-01T00:00:00Z')
ON CONFLICT (race_id, model_version_id, driver_id) DO NOTHING;

INSERT INTO race_results (race_id, driver_id, constructor_id, grid_position, finish_position, points, status)
VALUES
    (1, 1, 1, 1, 1, 25.0, 'Finished'),
    (1, 2, 1, 2, 2, 18.0, 'Finished')
ON CONFLICT (race_id, driver_id) DO NOTHING;

SELECT setval(pg_get_serial_sequence('circuits', 'id'), 1, TRUE);
SELECT setval(pg_get_serial_sequence('constructors', 'id'), 1, TRUE);
SELECT setval(pg_get_serial_sequence('drivers', 'id'), 2, TRUE);
SELECT setval(pg_get_serial_sequence('races', 'id'), 1, TRUE);
SELECT setval(pg_get_serial_sequence('model_versions', 'id'), 1, TRUE);
