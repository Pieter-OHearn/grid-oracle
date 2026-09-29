"""Safe, explicit bridge from the legacy SQL schema to Alembic.

This command never calls ``create_all`` or initialization SQL.  A versionless
database must prove that it is the known legacy schema before it is stamped;
anything else is refused for operator review.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

LEGACY_CORE_TABLES = frozenset(
    {
        "circuits",
        "constructors",
        "driver_contracts",
        "drivers",
        "evaluation_metrics",
        "features",
        "model_versions",
        "predictions",
        "qualifying_results",
        "race_results",
        "races",
        "weather_snapshots",
    }
)
LEGACY_BASELINE = "20260929_01"


class DatabaseMigrationError(RuntimeError):
    """Raised when a database cannot be safely identified for an upgrade."""


@dataclass(frozen=True)
class MigrationPlan:
    database_state: str
    missing_legacy_tables: tuple[str, ...]
    action: str


def inspect_database(database_url: str) -> MigrationPlan:
    """Identify only known states; do not mutate a connection."""
    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    if "alembic_version" in tables:
        return MigrationPlan("alembic_managed", (), "upgrade head")
    missing = tuple(sorted(LEGACY_CORE_TABLES - tables))
    if missing:
        return MigrationPlan("unrecognized", missing, "refuse")
    return MigrationPlan(
        "recognized_legacy", (), f"stamp {LEGACY_BASELINE}, then upgrade head"
    )


def _alembic_config(database_url: str) -> Config:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_database(database_url: str, *, dry_run: bool = False) -> MigrationPlan:
    """Upgrade an existing recognized database without reinitializing it."""
    plan = inspect_database(database_url)
    if plan.database_state == "unrecognized":
        missing = ", ".join(plan.missing_legacy_tables)
        raise DatabaseMigrationError(
            "refusing to create or reset an unrecognized database; missing "
            "legacy tables: " + missing
        )
    if dry_run:
        return plan
    config = _alembic_config(database_url)
    if plan.database_state == "recognized_legacy":
        command.stamp(config, LEGACY_BASELINE)
    command.upgrade(config, "head")
    return plan


def downgrade_wp02(database_url: str, *, dry_run: bool = False) -> MigrationPlan:
    """Remove additive WP02 structures before restoring a legacy backup."""
    plan = inspect_database(database_url)
    if plan.database_state != "alembic_managed":
        raise DatabaseMigrationError(
            "WP02 rollback requires an Alembic-managed database"
        )
    rollback_plan = MigrationPlan(
        "alembic_managed", (), f"downgrade to {LEGACY_BASELINE}"
    )
    if not dry_run:
        command.downgrade(_alembic_config(database_url), LEGACY_BASELINE)
    return rollback_plan


def finalize_legacy_restore(
    database_url: str, *, dry_run: bool = False
) -> MigrationPlan:
    """Forget the baseline ledger only after a pre-ledger backup is restored."""
    engine = create_engine(database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        additive_tables = {
            "season_rulesets",
            "entity_aliases",
            "circuit_layouts",
            "event_sessions",
            "event_entries",
            "result_revisions",
            "identity_quarantine",
        }
        if "alembic_version" not in tables or additive_tables & tables:
            raise DatabaseMigrationError(
                "legacy restore is not ready: downgrade WP02 and restore the "
                "pre-ledger backup first"
            )
        with engine.connect() as connection:
            revision = connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one()
        if revision != LEGACY_BASELINE:
            raise DatabaseMigrationError(
                "legacy restore is not at the recognized baseline"
            )
        if not dry_run:
            with engine.begin() as connection:
                connection.exec_driver_sql("DROP TABLE alembic_version")
    finally:
        engine.dispose()
    return MigrationPlan("legacy_restored", (), "remove baseline Alembic ledger")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely upgrade a recognized GridOracle database."
    )
    parser.add_argument(
        "--database-url",
        required=True,
        help="Target database; never defaults from the environment",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect and print the planned ledger action only",
    )
    parser.add_argument(
        "--backup-path",
        type=Path,
        help="Existing database backup required for a real upgrade",
    )
    parser.add_argument(
        "--downgrade-wp02",
        action="store_true",
        help="Remove additive WP02 structures before restoring a legacy backup",
    )
    parser.add_argument(
        "--finalize-legacy-restore",
        action="store_true",
        help="Remove the baseline ledger after restoring a pre-WP02 backup",
    )
    args = parser.parse_args()
    if args.downgrade_wp02 and args.finalize_legacy_restore:
        parser.error("choose only one rollback phase per invocation")
    if not args.dry_run and (
        args.backup_path is None or not args.backup_path.is_file()
    ):
        parser.error("--backup-path must name an existing backup before a real upgrade")
    try:
        operation = (
            finalize_legacy_restore
            if args.finalize_legacy_restore
            else downgrade_wp02
            if args.downgrade_wp02
            else upgrade_database
        )
        plan = operation(args.database_url, dry_run=args.dry_run)
    except DatabaseMigrationError as exc:
        parser.error(str(exc))
    print(f"database_state={plan.database_state}; action={plan.action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
