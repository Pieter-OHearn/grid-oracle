"""Provider boundary: polite retrieval, immutable raw snapshots and quarantine."""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Mapping

import requests


class ProviderContractError(ValueError):
    pass


@dataclass(frozen=True)
class RateBudget:
    requests_per_window: int = 30
    window_seconds: float = 60.0


class ProviderAdapter:
    def __init__(
        self,
        name: str,
        user_agent: str,
        snapshot_root: Path,
        budget: RateBudget = RateBudget(),
        sleep: Callable[[float], None] = time.sleep,
        random_source: Callable[[], float] = random.random,
    ):
        self.name, self.user_agent, self.snapshot_root, self.budget = name, user_agent, snapshot_root, budget
        self.sleep, self.random = sleep, random_source
        self._started, self._used = time.monotonic(), 0

    def _budget_wait(self) -> None:
        elapsed = time.monotonic() - self._started
        if self._used >= self.budget.requests_per_window and elapsed < self.budget.window_seconds:
            self.sleep(self.budget.window_seconds - elapsed)
            self._started, self._used = time.monotonic(), 0
        elif elapsed >= self.budget.window_seconds:
            self._started, self._used = time.monotonic(), 0

    def fetch_json(
        self,
        url: str,
        *,
        validator: Callable[[Mapping[str, Any]], None],
        params: Mapping[str, Any] | None = None,
        attempts: int = 4,
        session: requests.Session | Any = requests,
    ) -> tuple[dict[str, Any], Path]:
        error: Exception | None = None
        for attempt in range(attempts):
            self._budget_wait()
            try:
                response = session.get(url, params=params, headers={"User-Agent": self.user_agent}, timeout=(5, 30))
                self._used += 1
                if response.status_code == 429:
                    raise requests.HTTPError("429 rate limited", response=response)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ProviderContractError("provider payload must be an object")
                validator(payload)
                return payload, self._snapshot(payload)
            except (
                requests.Timeout,
                requests.ConnectionError,
                requests.HTTPError,
                ValueError,
                ProviderContractError,
            ) as exc:
                error = exc
                if attempt + 1 < attempts:
                    self.sleep(min(30.0, 0.5 * 2**attempt) + self.random() * 0.25)
        assert error is not None
        self._quarantine(url, str(error))
        raise error

    def _snapshot(self, payload: Mapping[str, Any]) -> Path:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        digest = sha256(raw).hexdigest()
        path = self.snapshot_root / self.name / f"{digest}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def _quarantine(self, url: str, reason: str) -> Path:
        raw = json.dumps(
            {"provider": self.name, "url": url, "reason": reason, "at": datetime.now(UTC).isoformat()}, sort_keys=True
        ).encode()
        digest = sha256(raw).hexdigest()
        path = self.snapshot_root / "quarantine" / f"{digest}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path


def require_keys(*keys: str) -> Callable[[Mapping[str, Any]], None]:
    def validate(payload: Mapping[str, Any]) -> None:
        missing = [key for key in keys if key not in payload]
        if missing:
            raise ProviderContractError(f"provider payload missing required keys: {', '.join(missing)}")

    return validate
