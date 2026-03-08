-- TICKET 003 — Add unique constraints required for idempotent upserts

ALTER TABLE circuits
    ADD CONSTRAINT circuits_name_unique UNIQUE (name);

ALTER TABLE races
    ADD CONSTRAINT races_season_round_unique UNIQUE (season, round);

ALTER TABLE constructors
    ADD CONSTRAINT constructors_name_unique UNIQUE (name);
