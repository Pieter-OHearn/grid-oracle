-- TICKET 004 — Add latitude/longitude to circuits for weather lookups

ALTER TABLE circuits
    ADD COLUMN IF NOT EXISTS latitude  NUMERIC(9, 6),
    ADD COLUMN IF NOT EXISTS longitude NUMERIC(9, 6);

-- Seed coordinates for known F1 circuits.
-- Circuit names match FastF1 EventName values stored by upsert_circuit().
UPDATE circuits SET latitude = 26.0325,  longitude = 50.5106   WHERE name = 'Bahrain Grand Prix';
UPDATE circuits SET latitude = 21.6319,  longitude = 39.1044   WHERE name = 'Saudi Arabian Grand Prix';
UPDATE circuits SET latitude = -37.8497, longitude = 144.9680  WHERE name = 'Australian Grand Prix';
UPDATE circuits SET latitude = 30.1328,  longitude = 51.5686   WHERE name = 'Japanese Grand Prix';
UPDATE circuits SET latitude = 24.4672,  longitude = 54.6031   WHERE name = 'Abu Dhabi Grand Prix';
UPDATE circuits SET latitude = 25.4900,  longitude = 51.4543   WHERE name = 'Qatar Grand Prix';
UPDATE circuits SET latitude = 1.2914,   longitude = 103.8640  WHERE name = 'Singapore Grand Prix';
UPDATE circuits SET latitude = 31.3389,  longitude = 121.2200  WHERE name = 'Chinese Grand Prix';
UPDATE circuits SET latitude = 19.4042,  longitude = -99.0907  WHERE name = 'Mexico City Grand Prix';
UPDATE circuits SET latitude = -23.7036, longitude = -46.6997  WHERE name = 'São Paulo Grand Prix';
UPDATE circuits SET latitude = 25.9581,  longitude = -80.2389  WHERE name = 'Miami Grand Prix';
UPDATE circuits SET latitude = 36.1162,  longitude = -115.1745 WHERE name = 'Las Vegas Grand Prix';
UPDATE circuits SET latitude = 45.5017,  longitude = -73.5291  WHERE name = 'Canadian Grand Prix';
UPDATE circuits SET latitude = 40.3725,  longitude = -3.7436   WHERE name = 'Spanish Grand Prix';
UPDATE circuits SET latitude = 47.2197,  longitude = 14.7647   WHERE name = 'Austrian Grand Prix';
UPDATE circuits SET latitude = 52.0786,  longitude = -1.0169   WHERE name = 'British Grand Prix';
UPDATE circuits SET latitude = 50.4372,  longitude = 5.9714    WHERE name = 'Belgian Grand Prix';
UPDATE circuits SET latitude = 52.3388,  longitude = 4.5409    WHERE name = 'Dutch Grand Prix';
UPDATE circuits SET latitude = 45.6156,  longitude = 9.2811    WHERE name = 'Italian Grand Prix';
UPDATE circuits SET latitude = 46.9591,  longitude = 7.4474    WHERE name = 'Emilia Romagna Grand Prix';
UPDATE circuits SET latitude = 43.7347,  longitude = 7.4206    WHERE name = 'Monaco Grand Prix';
UPDATE circuits SET latitude = 44.3439,  longitude = 11.7167   WHERE name = 'Azerbaijan Grand Prix';
UPDATE circuits SET latitude = 47.5832,  longitude = 19.2526   WHERE name = 'Hungarian Grand Prix';
UPDATE circuits SET latitude = 34.8431,  longitude = 136.5407  WHERE name = 'United States Grand Prix';
