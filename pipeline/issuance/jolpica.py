"""Live Jolpica (Ergast-compatible) reads through the polite provider boundary.

Every read returns the exact payload with its retrieval time. Callers store
that payload as an immutable raw snapshot before deriving anything from it, so
a forecast can always be traced to the provider bytes it used.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from gridoracle.ops.bundle import canonical

from pipeline.ingest.provider import (
    ProviderAdapter,
    ProviderContractError,
    RateBudget,
)

BASE_URL = "https://api.jolpi.ca/ergast/f1"
USER_AGENT = "GridOracle production issuance (+https://github.com/Pieter-OHearn/grid-oracle)"
PAGE = 100
# Jolpica allows 4 requests a second and 500 an hour; stay well inside both.
BUDGET = RateBudget(requests_per_window=60, window_seconds=600.0)


@dataclass(frozen=True)
class Observation:
    """One provider read: the merged payload and when it was retrieved."""

    kind: str
    url: str
    payload: dict[str, Any]
    retrieved_at: datetime

    def races(self) -> list[dict[str, Any]]:
        return self.payload["MRData"]["RaceTable"]["Races"]

    def document(self) -> dict[str, Any]:
        """The canonical artifact recorded as the raw snapshot."""
        return {
            "provider": "jolpica",
            "kind": self.kind,
            "url": self.url,
            "retrieved_at": self.retrieved_at.isoformat(),
            "payload": self.payload,
        }

    def content(self) -> bytes:
        return canonical(self.document())


def _race_table(payload: Mapping[str, Any]) -> None:
    try:
        races = payload["MRData"]["RaceTable"]["Races"]
        int(payload["MRData"]["total"])
    except (KeyError, TypeError, ValueError) as error:
        raise ProviderContractError("Jolpica payload has no race table") from error
    if not isinstance(races, list):
        raise ProviderContractError("Jolpica race table is not a list")


class JolpicaClient:
    def __init__(
        self,
        snapshot_root: Path,
        *,
        session: requests.Session | Any = requests,
        base_url: str = BASE_URL,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        adapter: ProviderAdapter | None = None,
    ):
        self.session, self.base_url, self.now = session, base_url.rstrip("/"), now
        self.adapter = adapter or ProviderAdapter("jolpica", USER_AGENT, snapshot_root, BUDGET)

    def schedule(self, season: int) -> Observation:
        return self._read("schedule", f"{season}/races/")

    def results(self, season: int, round_number: int | None = None) -> Observation:
        path = f"{season}/results/" if round_number is None else f"{season}/{round_number}/results/"
        return self._read("results", path)

    def qualifying(self, season: int, round_number: int) -> Observation:
        return self._read("qualifying", f"{season}/{round_number}/qualifying/")

    def _read(self, kind: str, path: str) -> Observation:
        """Read every page and merge rows of the same race in provider order."""
        url = f"{self.base_url}/{path}"
        retrieved_at = self.now()
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        order: list[tuple[str, str]] = []
        offset, total, first = 0, None, None
        while total is None or offset < total:
            payload, _ = self.adapter.fetch_json(
                url,
                validator=_race_table,
                params={"limit": PAGE, "offset": offset},
                session=self.session,
            )
            data = payload["MRData"]
            total = int(data["total"])
            first = first or payload
            for race in data["RaceTable"]["Races"]:
                key = (str(race["season"]), str(race["round"]))
                if key not in merged:
                    merged[key] = {k: v for k, v in race.items()}
                    order.append(key)
                    continue
                for field in ("Results", "QualifyingResults"):
                    if field in race:
                        merged[key].setdefault(field, []).extend(race[field])
            if not data["RaceTable"]["Races"] or kind == "schedule":
                break
            offset += PAGE
        assert first is not None
        mr_data = {key: value for key, value in first["MRData"].items() if key not in {"limit", "offset", "RaceTable"}}
        table = {key: value for key, value in first["MRData"]["RaceTable"].items() if key != "Races"}
        table["Races"] = [merged[key] for key in order]
        return Observation(
            kind=kind,
            url=url,
            payload={"MRData": {**mr_data, "RaceTable": table}},
            retrieved_at=retrieved_at,
        )
