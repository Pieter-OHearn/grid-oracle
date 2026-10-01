"""One-shot backup-gated production migration; never called by API startup."""

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from gridoracle.ops.recovery import inventory, verify_recovery_set
from gridoracle.ops.runtime import configure
from scripts.db_migrate import upgrade_database


def migrate(directory: Path, receipt_sha256: str, *, bootstrap_empty=False) -> None:
    receipt = verify_recovery_set(directory, receipt_sha256)
    created = datetime.fromisoformat(receipt["created_at"])
    now = datetime.now(UTC)
    if not now - timedelta(hours=24) <= created <= now + timedelta(minutes=5):
        raise ValueError("migration backup is older than 24 hours")
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.connect() as conn:
            identity = conn.execute(text("SELECT current_database()")).scalar_one()
        if receipt["database"] != identity:
            raise ValueError("backup belongs to another database")
        tables = inspect(engine).get_table_names()
        if "alembic_version" in tables:
            with engine.connect() as conn:
                revision = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
            if revision != receipt["schema_revision"]:
                raise ValueError("schema changed since backup; take a new backup")
        if (
            receipt["lineage"] is not None
            and inventory(engine, directory / "artifacts") != receipt["lineage"]
        ):
            raise ValueError("lineage changed since backup; quiesce writers and repeat")
        if not tables:
            if not bootstrap_empty:
                raise ValueError("empty database requires explicit --bootstrap-empty")
            # The historical SQL baseline exists only for a fresh empty target.
            # Existing installations go through the integrated inspector/ledger.
            raw = engine.raw_connection()
            try:
                with raw.cursor() as cursor:
                    for path in sorted(Path("db/migrations").glob("*.sql")):
                        cursor.execute(path.read_text())
                raw.commit()
            finally:
                raw.close()
        upgrade_database(os.environ["DATABASE_URL"])
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", required=True, type=Path)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--bootstrap-empty", action="store_true")
    args = parser.parse_args()
    configure()
    migrate(args.backup, args.receipt_sha256, bootstrap_empty=args.bootstrap_empty)
    print(json.dumps({"event": "schema-upgrade", "status": "succeeded"}))


if __name__ == "__main__":
    main()
