"""Seal/check a coordinated database dump plus complete artifact directory.

The caller stops writers, creates a pg_dump --format=custom archive with the
matching PostgreSQL client, then seals it. Restore never overwrites a database.
"""

import argparse
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from gridoracle.ops.bundle import verify_bundle
from gridoracle.ops.recovery import file_hash, inventory, verify_recovery_set
from gridoracle.ops.runtime import configure


def seal(directory: Path, artifacts: Path, bundle: Path, bundle_hash: str) -> str:
    if (directory / "recovery.json").exists():
        raise ValueError("refusing to replace a sealed recovery set")
    if (
        not (directory / "database.dump").is_file()
        or (directory / "database.dump").stat().st_size == 0
    ):
        raise ValueError("a nonempty custom pg_dump archive is required")
    verify_bundle(artifacts, bundle, bundle_hash)
    if any(path.is_symlink() for path in artifacts.rglob("*")):
        raise ValueError("artifact backup must not contain symlinks")
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.connect() as conn:
            database = conn.execute(text("SELECT current_database()")).scalar_one()
        tables = inspect(engine).get_table_names()
        lineage = inventory(engine, artifacts) if "forecast_runs" in tables else None
        with engine.connect() as conn:
            revision = (
                conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                if "alembic_version" in tables
                else None
            )
        shutil.copytree(artifacts, directory / "artifacts", symlinks=False)
        shutil.copyfile(bundle, directory / "bundle.json")
        files = {
            p.relative_to(directory).as_posix(): file_hash(p)
            for p in directory.rglob("*")
            if p.is_file()
        }
        receipt = {
            "format": "gridoracle-recovery-v1",
            "created_at": datetime.now(UTC).isoformat(),
            "database": database,
            "schema_revision": revision,
            "lineage": lineage,
            "files": files,
        }
        (directory / "recovery.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n"
        )
        return file_hash(directory / "recovery.json")
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seal", "verify", "compare"))
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--receipt-sha256")
    args = parser.parse_args()
    if args.action == "seal":
        configure()
        print(
            seal(
                args.directory,
                Path(os.environ["GRIDORACLE_ARTIFACT_ROOT"]),
                Path(os.environ["GRIDORACLE_BUNDLE_FILE"]),
                os.environ["GRIDORACLE_BUNDLE_SHA256"],
            )
        )
        return
    if not args.receipt_sha256:
        parser.error("verify/compare requires an externally retained --receipt-sha256")
    receipt = verify_recovery_set(args.directory, args.receipt_sha256)
    if args.action == "compare":
        configure()
        engine = create_engine(os.environ["DATABASE_URL"])
        try:
            if inventory(engine, args.directory / "artifacts") != receipt["lineage"]:
                raise ValueError("restored forecast/lineage hashes differ")
            with engine.connect() as conn:
                revision = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
            if revision != receipt["schema_revision"]:
                raise ValueError("restored schema revision differs")
        finally:
            engine.dispose()
    print(json.dumps({"status": "verified", "receipt_sha256": args.receipt_sha256}))


if __name__ == "__main__":
    main()
