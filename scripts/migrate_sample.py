"""Upgrade only the disposable, committed Compose sample before API startup."""

import os

from sqlalchemy import create_engine, text

from scripts.db_migrate import DatabaseMigrationError, upgrade_database


def migrate_sample(database_url: str, *, sample_data: str | None) -> None:
    if sample_data != "1":
        raise DatabaseMigrationError(
            "sample migration requires GRIDORACLE_SAMPLE_DATA=1"
        )
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            races = conn.execute(text("SELECT id, name FROM races")).all()
        if races != [(1, "Sample Grand Prix")]:
            raise DatabaseMigrationError(
                "sample migration requires the committed demo calendar"
            )
    finally:
        engine.dispose()
    # The dedicated sample volume contains disposable hand-authored data.
    # Real databases still use db_migrate's explicit backup-gated CLI.
    upgrade_database(database_url)


def main() -> None:
    migrate_sample(
        os.environ["DATABASE_URL"], sample_data=os.getenv("GRIDORACLE_SAMPLE_DATA")
    )
    print("Disposable sample database upgraded")


if __name__ == "__main__":
    main()
