-- TICKET 004 — Add latitude/longitude to circuits for weather lookups
-- Coordinates are populated dynamically via OpenWeatherMap geocoding
-- when fetch_weather.py runs for a race whose circuit lacks them.

ALTER TABLE circuits
    ADD COLUMN IF NOT EXISTS latitude  NUMERIC(9, 6),
    ADD COLUMN IF NOT EXISTS longitude NUMERIC(9, 6);
