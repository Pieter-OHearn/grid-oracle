"""Append-only experiment events. Deliberately no production model selector."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pipeline.benchmark.artifacts import read_json, write_once


class Registry:
    def __init__(self, root: Path):
        self.root = root

    def start(self, metadata: dict) -> str:
        identifier = f"wp06-{uuid4().hex}"
        write_once(
            self.root / identifier / "started.json",
            {"id": identifier, "status": "started", "at": datetime.now(UTC).isoformat(), "metadata": metadata},
        )
        return identifier

    def finish(self, identifier: str, *, result: dict | None = None, error: Exception | None = None) -> None:
        directory = self.root / identifier
        read_json(directory / "started.json")
        write_once(
            directory / "finished.json",
            {
                "id": identifier,
                "status": "failed" if error else "succeeded",
                "at": datetime.now(UTC).isoformat(),
                "error": f"{type(error).__name__}: {error}" if error else None,
                "result": result,
                "promotion": "not_authorized; independent review required",
            },
        )

    def records(self) -> list[dict]:
        return [read_json(path) for path in sorted(self.root.glob("*/started.json"))]
