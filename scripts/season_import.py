"""Validate and preview a new-season configuration without touching a database."""

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from gridoracle.domain.season import SeasonImportConfig


def load_config(path: Path) -> SeasonImportConfig:
    """Read a JSON configuration and return a strictly validated contract."""
    return SeasonImportConfig.model_validate_json(path.read_text(encoding="utf-8"))


def dry_run_summary(config: SeasonImportConfig) -> dict[str, object]:
    """Produce a serializable plan. This function intentionally has no I/O."""
    return {
        "schema_version": config.schema_version,
        "season": config.season,
        "ruleset_version": config.ruleset_version,
        "event_count": len(config.events),
        "events": [
            {
                "event_key": event.event_key,
                "round": event.round,
                "state": event.state,
                "session_kinds": [session.kind for session in event.sessions],
                "entry_count": len(event.entries),
            }
            for event in sorted(config.events, key=lambda item: item.round)
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and dry-run a GridOracle season import."
    )
    parser.add_argument(
        "--config", required=True, type=Path, help="JSON configuration to validate"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        required=True,
        help="Required: this WP02 command never imports data",
    )
    parser.add_argument(
        "--print-schema",
        action="store_true",
        help="Print the JSON schema before validating",
    )
    args = parser.parse_args()
    if args.print_schema:
        print(
            json.dumps(SeasonImportConfig.model_json_schema(), indent=2, sort_keys=True)
        )
    try:
        config = load_config(args.config)
    except (OSError, ValidationError, ValueError) as exc:
        parser.error(f"invalid season configuration: {exc}")
    print(json.dumps(dry_run_summary(config), indent=2, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
