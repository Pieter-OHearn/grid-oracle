"""The opt-in sample bridge preserves demo facts and refuses other calendars."""

import pytest
from sqlalchemy import create_engine, inspect, text

from scripts.db_migrate import DatabaseMigrationError
from scripts.migrate_sample import migrate_sample
from scripts.tests.test_db_migrate import create_populated_legacy_fixture


def sample_database(tmp_path):
    url = f"sqlite:///{tmp_path / 'sample.sqlite'}"
    create_populated_legacy_fixture(url)
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE races ADD COLUMN name TEXT"))
        conn.execute(text("DELETE FROM races WHERE id = 2"))
        conn.execute(text("UPDATE races SET name = 'Sample Grand Prix' WHERE id = 1"))
    return url, engine


def test_sample_upgrade_is_idempotent_and_preserves_facts(tmp_path):
    url, engine = sample_database(tmp_path)
    try:
        migrate_sample(url, sample_data="1")
        migrate_sample(url, sample_data="1")
        assert {"season_rulesets", "forecast_publications"} <= set(
            inspect(engine).get_table_names()
        )
        with engine.connect() as conn:
            assert conn.execute(text("SELECT id, name FROM races")).all() == [
                (1, "Sample Grand Prix")
            ]
            assert conn.execute(text("SELECT count(*) FROM drivers")).scalar() == 1
    finally:
        engine.dispose()


@pytest.mark.parametrize("sample_data", [None, "0"])
def test_sample_upgrade_requires_explicit_opt_in(tmp_path, sample_data):
    url, engine = sample_database(tmp_path)
    try:
        with pytest.raises(DatabaseMigrationError, match="GRIDORACLE_SAMPLE_DATA"):
            migrate_sample(url, sample_data=sample_data)
        assert "alembic_version" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_sample_upgrade_refuses_another_calendar_without_mutation(tmp_path):
    url, engine = sample_database(tmp_path)
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO races (id, name) VALUES (2, 'Real race')"))
        with pytest.raises(DatabaseMigrationError, match="committed demo calendar"):
            migrate_sample(url, sample_data="1")
        assert "alembic_version" not in inspect(engine).get_table_names()
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM races")).scalar() == 2
    finally:
        engine.dispose()
