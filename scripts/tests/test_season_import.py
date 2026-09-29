from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from gridoracle.domain.season import SeasonImportConfig
from scripts.season_import import dry_run_summary


def valid_config() -> dict:
    return {
        "schema_version": "1.0",
        "season": 2027,
        "ruleset_version": "fia-2027.1",
        "events": [
            {
                "event_key": "event:2027:australia",
                "round": 1,
                "name": "Australian Grand Prix",
                "circuit_identity_key": "circuit:albert-park",
                "layout_identity_key": "layout:albert-park:gp",
                "state": "postponed",
                "sessions": [
                    {
                        "kind": "sprint",
                        "scheduled_at": datetime(2027, 3, 12, tzinfo=UTC),
                    },
                    {
                        "kind": "qualifying",
                        "scheduled_at": datetime(2027, 3, 13, tzinfo=UTC),
                    },
                    {"kind": "race", "scheduled_at": datetime(2027, 3, 14, tzinfo=UTC)},
                ],
                "entries": [
                    {
                        "driver_identity_key": "driver:one",
                        "team_identity_key": "team:renamed",
                        "role": "primary",
                    },
                    {
                        "driver_identity_key": "driver:reserve",
                        "team_identity_key": "team:renamed",
                        "role": "reserve",
                    },
                ],
            }
        ],
    }


def test_dry_run_accepts_sprint_reserve_and_postponement_without_database():
    config = SeasonImportConfig.model_validate(valid_config())
    summary = dry_run_summary(config)
    assert summary["event_count"] == 1
    assert summary["events"][0]["entry_count"] == 2
    assert summary["events"][0]["state"] == "postponed"


def test_config_rejects_missing_race_session():
    config = valid_config()
    config["events"][0]["sessions"] = config["events"][0]["sessions"][:2]
    with pytest.raises(ValidationError, match="exactly one race"):
        SeasonImportConfig.model_validate(config)


def test_config_rejects_duplicate_rounds():
    config = valid_config()
    duplicate = valid_config()["events"][0]
    duplicate["event_key"] = "event:2027:second"
    config["events"].append(duplicate)
    with pytest.raises(ValidationError, match="rounds must be unique"):
        SeasonImportConfig.model_validate(config)
