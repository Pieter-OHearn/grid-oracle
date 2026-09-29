"""Legacy identity report construction without unsafe name-based merges."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class LegacyIdentity:
    entity_kind: str
    legacy_id: int
    display_name: str | None
    identity_key: str | None


def build_legacy_identity_report(
    records: Iterable[LegacyIdentity],
) -> dict[str, object]:
    """Return deterministic assignments and collisions requiring quarantine.

    A collision is deliberately not resolved automatically. The report gives an
    operator the exact stable keys that need a curated alias/successor decision.
    """
    assignments: list[dict[str, object]] = []
    names: dict[tuple[str, str], list[LegacyIdentity]] = defaultdict(list)
    unresolved: list[dict[str, object]] = []
    for record in sorted(records, key=lambda item: (item.entity_kind, item.legacy_id)):
        identity_key = (
            record.identity_key or f"legacy:{record.entity_kind}:{record.legacy_id}"
        )
        assignments.append(
            {
                "entity_kind": record.entity_kind,
                "legacy_id": record.legacy_id,
                "identity_key": identity_key,
                "display_name": record.display_name,
            }
        )
        if not record.display_name or not record.display_name.strip():
            unresolved.append(
                {
                    "entity_kind": record.entity_kind,
                    "legacy_identifier": str(record.legacy_id),
                    "reason": "missing_display_name",
                }
            )
        else:
            names[(record.entity_kind, record.display_name.strip().casefold())].append(
                record
            )
    for (entity_kind, normalized_name), grouped in sorted(names.items()):
        if len(grouped) > 1:
            unresolved.append(
                {
                    "entity_kind": entity_kind,
                    "legacy_identifier": normalized_name,
                    "reason": "ambiguous_display_name",
                    "legacy_ids": [record.legacy_id for record in grouped],
                }
            )
    return {"assignments": assignments, "unresolved": unresolved}
