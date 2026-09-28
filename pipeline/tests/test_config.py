import pytest

from pipeline.config import ConfigurationError, load_pipeline_settings


def test_missing_database_url_has_actionable_error():
    with pytest.raises(ConfigurationError, match="Copy .env.example"):
        load_pipeline_settings({})


def test_scheduler_requires_weather_key_but_regular_pipeline_validation_does_not():
    env = {"DATABASE_URL": "sqlite:///:memory:"}
    assert load_pipeline_settings(env).openweather_api_key is None
    with pytest.raises(ConfigurationError, match="OPENWEATHER_API_KEY"):
        load_pipeline_settings(env, require_weather_key=True)
