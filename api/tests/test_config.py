import pytest

from api.config import ConfigurationError, load_api_settings


def test_missing_database_url_has_actionable_error():
    with pytest.raises(ConfigurationError, match="Copy .env.example"):
        load_api_settings({})


def test_invalid_database_url_has_actionable_error():
    with pytest.raises(ConfigurationError, match="postgresql"):
        load_api_settings({"DATABASE_URL": "mysql://example"})


def test_valid_sqlite_configuration_is_accepted_for_local_checks():
    settings = load_api_settings({"DATABASE_URL": "sqlite:///:memory:"})
    assert settings.database_url == "sqlite:///:memory:"
