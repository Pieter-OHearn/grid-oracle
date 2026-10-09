"""Recorded 2026 Jolpica payloads served page by page, as the live API does."""

from __future__ import annotations

import copy
import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

FIXTURE = Path(__file__).parent / "fixtures/wp15/jolpica-2026.json.gz"


def recorded() -> dict:
    return json.loads(gzip.decompress(FIXTURE.read_bytes()))


def _race_start(race: dict) -> datetime:
    value = f"{race['date']}T{race['time']}".replace("Z", "+00:00")
    return datetime.fromisoformat(value).astimezone(UTC)


class FakeJolpica:
    """A no-socket session: rows appear once their session has finished.

    `published` maps (kind, round) to whether the provider has the data yet;
    by default results appear an hour after the race start and qualifying an
    hour after qualifying starts, judged by the fake clock `now`.
    """

    def __init__(self, now, fixture: dict | None = None):
        self.fixture = fixture or recorded()
        self.now = now
        self.calls: list[tuple[str, dict]] = []
        self.published: dict[tuple[str, int], bool] = {}
        self.schedule = {int(race["round"]): race for race in self.fixture["schedule"]["MRData"]["RaceTable"]["Races"]}

    def _visible(self, kind: str, round_number: int) -> bool:
        if (kind, round_number) in self.published:
            return self.published[(kind, round_number)]
        race = self.schedule[round_number]
        if kind == "qualifying":
            block = race["Qualifying"]
            start = datetime.fromisoformat(f"{block['date']}T{block['time']}".replace("Z", "+00:00"))
        else:
            start = _race_start(race)
        return (self.now() - start).total_seconds() >= 3600

    def _payload(self, path: str) -> dict:
        parts = path.strip("/").split("/")
        if parts[1:] == ["races"]:
            return copy.deepcopy(self.fixture["schedule"])
        if parts[1:] == ["results"]:
            races = [
                copy.deepcopy(self.fixture["results"][key]["MRData"]["RaceTable"]["Races"][0])
                for key in sorted(self.fixture["results"], key=int)
                if self._visible("results", int(key))
            ]
            return {"MRData": {"total": "0", "RaceTable": {"season": parts[0], "Races": races}}}
        round_number = int(parts[1])
        kind = parts[2]
        source = self.fixture[kind].get(str(round_number))
        if source is None or not self._visible(kind, round_number):
            return {
                "MRData": {
                    "total": "0",
                    "RaceTable": {"season": parts[0], "round": parts[1], "Races": []},
                }
            }
        return copy.deepcopy(source)

    def get(self, url, params=None, headers=None, timeout=None):
        if not url.startswith("https://api.jolpi.ca/ergast/f1/"):
            raise AssertionError(f"unexpected provider URL {url}")
        params = dict(params or {})
        self.calls.append((url, params))
        payload = self._payload(url.split("/ergast/f1/", 1)[1])
        races = payload["MRData"]["RaceTable"]["Races"]
        field = next(
            (name for name in ("Results", "QualifyingResults") if races and name in races[0]),
            None,
        )
        if field is None:
            payload["MRData"]["total"] = str(len(races))
        else:
            # Jolpica pages by result row, repeating each race's header.
            rows = [(index, row) for index, race in enumerate(races) for row in race[field]]
            offset, limit = int(params.get("offset", 0)), int(params.get("limit", 30))
            page = rows[offset : offset + limit]
            sliced = []
            for index, race in enumerate(races):
                chosen = [row for i, row in page if i == index]
                if chosen:
                    sliced.append({**race, field: chosen})
            payload["MRData"]["RaceTable"]["Races"] = sliced
            payload["MRData"]["total"] = str(len(rows))
        payload["MRData"]["limit"] = str(params.get("limit", 30))
        payload["MRData"]["offset"] = str(params.get("offset", 0))
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(payload).encode()
        return response
