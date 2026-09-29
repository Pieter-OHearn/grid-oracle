"""Report legacy identity assignments and quarantine unresolved mappings."""

import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine, text

from gridoracle.domain.identity import LegacyIdentity, build_legacy_identity_report

_ENTITY_QUERIES = {
    "driver": (
        "SELECT id, full_name AS display_name, identity_key FROM drivers ORDER BY id"
    ),
    "team": (
        "SELECT id, name AS display_name, identity_key FROM constructors ORDER BY id"
    ),
    "circuit": (
        "SELECT id, name AS display_name, identity_key FROM circuits ORDER BY id"
    ),
}


def collect_report(database_url: str) -> dict[str, object]:
    """Read migrated identities; this function does not write or merge anything."""
    engine = create_engine(database_url)
    records: list[LegacyIdentity] = []
    try:
        with engine.connect() as connection:
            for entity_kind, query in _ENTITY_QUERIES.items():
                records.extend(
                    LegacyIdentity(
                        entity_kind, row.id, row.display_name, row.identity_key
                    )
                    for row in connection.execute(text(query))
                )
    finally:
        engine.dispose()
    return build_legacy_identity_report(records)


def quarantine_unresolved(database_url: str, report: dict[str, object]) -> int:
    """Persist only report findings. It never selects a merge or mutates legacy rows."""
    unresolved = report["unresolved"]
    assert isinstance(unresolved, list)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            for finding in unresolved:
                connection.execute(
                    text(
                        """
                        INSERT INTO identity_quarantine (
                            entity_kind, legacy_identifier, reason, details
                        )
                        VALUES (:entity_kind, :legacy_identifier, :reason, :details)
                        ON CONFLICT (entity_kind, legacy_identifier, reason) DO NOTHING
                        """
                    ),
                    {
                        "entity_kind": finding["entity_kind"],
                        "legacy_identifier": finding["legacy_identifier"],
                        "reason": finding["reason"],
                        "details": json.dumps(finding, sort_keys=True),
                    },
                )
    finally:
        engine.dispose()
    return len(unresolved)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a GridOracle legacy identity mapping report."
    )
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--quarantine",
        action="store_true",
        help="Write unresolved findings after migration",
    )
    args = parser.parse_args()
    report = collect_report(args.database_url)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.quarantine:
        print(f"quarantined={quarantine_unresolved(args.database_url, report)}")
    print(f"report={args.output}; unresolved={len(report['unresolved'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
