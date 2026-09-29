import shutil

import pytest
from sqlalchemy import create_engine, inspect, text

from scripts.db_migrate import (
    LEGACY_CORE_TABLES,
    DatabaseMigrationError,
    downgrade_wp02,
    finalize_legacy_restore,
    upgrade_database,
)


def create_populated_legacy_fixture(url: str) -> None:
    """Create only the legacy shape needed to test bridge recognition on SQLite."""
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            for table in sorted(LEGACY_CORE_TABLES):
                connection.execute(
                    text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
                )
            connection.execute(text("ALTER TABLE circuits ADD COLUMN name TEXT"))
            connection.execute(text("ALTER TABLE constructors ADD COLUMN name TEXT"))
            connection.execute(text("ALTER TABLE drivers ADD COLUMN full_name TEXT"))
            connection.execute(text("ALTER TABLE races ADD COLUMN season INTEGER"))
            connection.execute(
                text("INSERT INTO circuits (id, name) VALUES (1, 'Old Venue')")
            )
            connection.execute(
                text(
                    "INSERT INTO constructors (id, name) "
                    "VALUES (1, 'Team Before Rename')"
                )
            )
            connection.execute(
                text("INSERT INTO drivers (id, full_name) VALUES (1, 'Reserve Driver')")
            )
            connection.execute(
                text("INSERT INTO races (id, season) VALUES (1, 2025), (2, 2026)")
            )
    finally:
        engine.dispose()


def test_upgrade_populated_fixture_then_restore_backup(tmp_path):
    database = tmp_path / "legacy.sqlite"
    backup = tmp_path / "legacy-before-wp02.sqlite"
    url = f"sqlite:///{database}"
    create_populated_legacy_fixture(url)
    shutil.copy2(database, backup)

    plan = upgrade_database(url)
    assert plan.database_state == "recognized_legacy"
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        assert {"season_rulesets", "event_entries", "identity_quarantine"} <= set(
            inspector.get_table_names()
        )
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT identity_key FROM drivers WHERE id = 1")
                ).scalar_one()
                == "legacy:driver:1"
            )
            assert (
                connection.execute(text("SELECT count(*) FROM races")).scalar_one() == 2
            )
    finally:
        engine.dispose()

    downgrade_wp02(url)
    finalize_legacy_restore(url)
    after_rollback = create_engine(url)
    try:
        assert "alembic_version" not in inspect(after_rollback).get_table_names()
        with after_rollback.connect() as connection:
            assert (
                connection.execute(text("SELECT count(*) FROM races")).scalar_one() == 2
            )
    finally:
        after_rollback.dispose()

    shutil.copy2(backup, database)
    restored = create_engine(url)
    try:
        assert "alembic_version" not in inspect(restored).get_table_names()
        with restored.connect() as connection:
            assert (
                connection.execute(text("SELECT count(*) FROM races")).scalar_one() == 2
            )
    finally:
        restored.dispose()


def test_unknown_database_is_refused_without_reset(tmp_path):
    url = f"sqlite:///{tmp_path / 'unknown.sqlite'}"
    with pytest.raises(DatabaseMigrationError, match="refusing to create or reset"):
        upgrade_database(url)
