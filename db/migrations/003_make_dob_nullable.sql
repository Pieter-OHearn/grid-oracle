-- TICKET 003 — Make drivers.date_of_birth nullable
-- FastF1 no longer provides date_of_birth since Ergast was shut down.
ALTER TABLE drivers ALTER COLUMN date_of_birth DROP NOT NULL;
