"""Content fingerprints and atomic write-once artifact storage."""

from __future__ import annotations

import json
import os
from hashlib import sha256
from pathlib import Path
from tempfile import mkstemp

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "docs/benchmark"
CONTRACT = BENCHMARK / "v2"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def digest(value: object) -> str:
    return sha256(canonical(value)).hexdigest()


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_bytes_once(path: Path, content: bytes) -> None:
    """Use the provenance store's fsync/link pattern with exclusive named files.

    Unlike the content-addressed store, an existing event name is always an
    error, even when bytes match. No incomplete destination becomes visible.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = mkstemp(prefix=".benchmark-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_once(path: Path, value: object) -> None:
    content = canonical(value)  # Fail serialization before creating any file.
    write_bytes_once(path, content)


def verify_lock() -> dict:
    lock = read_json(CONTRACT / "lock.json")
    for name, expected in lock["files"].items():
        if file_hash(ROOT / name) != expected:
            raise ValueError(f"locked artifact changed: {name}; register a new protocol")
    return lock
