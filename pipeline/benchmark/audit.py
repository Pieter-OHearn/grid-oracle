"""Reproduce the prior descriptive audit without contacting any provider."""

from __future__ import annotations

import subprocess
import sys
import tarfile
from pathlib import Path

from pipeline.benchmark.artifacts import ROOT, file_hash, read_json
from pipeline.benchmark.data import ARCHIVE


def reproduce_audit(scratch: Path) -> dict:
    cache = scratch / "descriptive-cache"
    cache.mkdir(parents=True, exist_ok=True)
    with tarfile.open(ARCHIVE) as archive:
        for member in archive.getmembers():
            if member.isfile() and member.name.endswith(".json") and not Path(member.name).name.startswith("._"):
                handle = archive.extractfile(member)
                assert handle is not None
                (cache / Path(member.name).name).write_bytes(handle.read())
    output = scratch / "descriptive-audit.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "docs/evidence/baseline_audit.py"),
            "--cache",
            str(cache),
            "--offline",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    actual = read_json(output)
    expected = read_json(ROOT / "docs/evidence/baseline-summary.json")
    actual.pop("retrieved_at")
    expected.pop("retrieved_at")
    if actual != expected:
        raise ValueError("prior descriptive audit differs from archived summary")
    return {
        "status": "reproduced_exactly_except_retrieved_at",
        "source_summary_sha256": file_hash(ROOT / "docs/evidence/baseline-summary.json"),
        "interpretation": "descriptive provider numeric-order audit; not the WP06 target or an as-of score",
        "summary": actual,
    }
