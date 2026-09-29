"""Content fingerprints and write-once artifact storage."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "docs/benchmark"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def digest(value: object) -> str:
    return sha256(canonical(value)).hexdigest()


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_once(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(canonical(value))


def verify_lock() -> dict:
    lock = read_json(BENCHMARK / "lock.json")
    for name, expected in lock["files"].items():
        if file_hash(ROOT / name) != expected:
            raise ValueError(f"locked artifact changed: {name}; register a new protocol")
    return lock
