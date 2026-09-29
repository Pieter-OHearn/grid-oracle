from sqlalchemy import create_engine, text

from scripts.db_migrate import upgrade_database
from scripts.tests.test_db_migrate import create_populated_legacy_fixture


def test_two_seasons_support_variable_fields_sprints_transfers_and_revisions(tmp_path):
    """The database does not encode a 20/22-car assumption or a single event state."""
    url = f"sqlite:///{tmp_path / 'domain.sqlite'}"
    create_populated_legacy_fixture(url)
    upgrade_database(url)
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO event_sessions "
                    "(race_id, kind, scheduled_at, revision, status) "
                    "VALUES (1, 'sprint', CURRENT_TIMESTAMP, 1, 'completed'), "
                    "(1, 'race', CURRENT_TIMESTAMP, 1, 'completed'), "
                    "(2, 'race', CURRENT_TIMESTAMP, 1, 'postponed'), "
                    "(2, 'race', CURRENT_TIMESTAMP, 2, 'scheduled')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO event_entries "
                    "(race_id, driver_id, constructor_id, role, status, revision) "
                    "VALUES (1, 1, 1, 'reserve', 'withdrawn', 1), "
                    "(1, 1, 1, 'primary', 'active', 2)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO result_revisions "
                    "(race_id, revision, source, reason, is_official) "
                    "VALUES (1, 1, 'fixture', 'provisional', 0), "
                    "(1, 2, 'fixture', 'official correction', 1)"
                )
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM event_sessions WHERE race_id = 1")
                ).scalar_one()
                == 2
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM event_entries WHERE race_id = 1")
                ).scalar_one()
                == 2
            )
            assert (
                connection.execute(
                    text("SELECT max(revision) FROM result_revisions WHERE race_id = 1")
                ).scalar_one()
                == 2
            )
    finally:
        engine.dispose()
