#!/usr/bin/env bash
# Load only the committed static demo fixture into the isolated sample volume.
set -euo pipefail

if [ "${GRIDORACLE_SAMPLE_DATA:-0}" != "1" ]; then
    echo "Static sample data disabled."
    exit 0
fi

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" \
    -f /sample/001_static_demo.sql
echo "Loaded GridOracle static sample data."
