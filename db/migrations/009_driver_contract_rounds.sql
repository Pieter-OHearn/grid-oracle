BEGIN;

ALTER TABLE driver_contracts
    ADD COLUMN start_round INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN end_round INTEGER;

UPDATE driver_contracts SET start_round = 1 WHERE start_round IS NULL;

ALTER TABLE driver_contracts
    DROP CONSTRAINT IF EXISTS driver_contracts_driver_id_season_key;

ALTER TABLE driver_contracts
    ADD CONSTRAINT driver_contracts_driver_id_season_start_round_key
        UNIQUE (driver_id, season, start_round);

CREATE INDEX IF NOT EXISTS idx_driver_contracts_driver_season_start_round
    ON driver_contracts (driver_id, season, start_round);

CREATE INDEX IF NOT EXISTS idx_driver_contracts_season_round_window
    ON driver_contracts (season, start_round, COALESCE(end_round, 10_000));

-- Normalise constructor colours in the database so the API and frontend can rely on the stored value.
UPDATE constructors SET color_hex = '#3671C6' WHERE name = 'Red Bull';
UPDATE constructors SET color_hex = '#E8002D' WHERE name = 'Ferrari';
UPDATE constructors SET color_hex = '#27F4D2' WHERE name = 'Mercedes';
UPDATE constructors SET color_hex = '#FF8000' WHERE name = 'McLaren';
UPDATE constructors SET color_hex = '#229971' WHERE name = 'Aston Martin';
UPDATE constructors SET color_hex = '#FF87BC' WHERE name = 'Alpine';
UPDATE constructors SET color_hex = '#64C4FF' WHERE name = 'Williams';
UPDATE constructors SET color_hex = '#6692FF' WHERE name = 'Racing Bulls';
UPDATE constructors SET color_hex = '#B6BABD' WHERE name = 'Haas';
UPDATE constructors SET color_hex = '#52E252' WHERE name = 'Audi';
UPDATE constructors SET color_hex = '#CC0000' WHERE name = 'Cadillac';

COMMIT;
