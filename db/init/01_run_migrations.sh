#!/usr/bin/env bash
# Apply all numbered SQL migrations in order.
# This script is placed in /docker-entrypoint-initdb.d/ and runs once when
# the PostgreSQL data directory is first initialised.
set -euo pipefail

MIGRATIONS_DIR="/migrations"

for sql_file in $(ls "${MIGRATIONS_DIR}"/*.sql 2>/dev/null | sort); do
    echo "Applying migration: ${sql_file}"
    psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" -f "${sql_file}"
done

echo "All migrations applied successfully."
