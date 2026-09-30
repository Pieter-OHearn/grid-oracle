"""Run provenance with separate deterministic input and volatile compute metadata."""

from __future__ import annotations

import importlib.metadata
import os
import platform
import resource
import subprocess
import sys
from pathlib import Path

from pipeline.benchmark.artifacts import ROOT, digest, file_hash


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def source_hashes() -> dict:
    paths = [
        *sorted((ROOT / "pipeline/benchmark").glob("*.py")),
        *sorted((ROOT / "pipeline/tests").glob("test_benchmark*.py")),
        ROOT / "pipeline/dataset/historical.py",
        ROOT / "gridoracle/domain/results.py",
        ROOT / "gridoracle/domain/targets.py",
        ROOT / "docs/evidence/baseline_audit.py",
    ]
    return {str(path.relative_to(ROOT)): file_hash(path) for path in paths}


def metadata(config: dict) -> dict:
    hashes = source_hashes()
    return {
        "git_revision": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")),
        "code_sha256": digest(hashes),
        "code_files": hashes,
        "dependency_lock_sha256": file_hash(ROOT / "uv.lock"),
        "python": sys.version,
        "versions": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "pyarrow", "pytest")},
        "seed": config["seed"],
        "compute": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or "not reported",
            "cpu_count": os.cpu_count(),
            "accelerator": "none; CPU only",
            "threads": {
                name: os.environ.get(name, "library default")
                for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
            },
        },
    }


def peak_rss_mib() -> float:
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / divisor


def check_source_revision(manifest: dict, revision: str) -> None:
    """Verify a later review commit contains exactly the measured source bytes."""
    for path, expected in manifest["code_files"].items():
        from hashlib import sha256

        content = subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT)
        if sha256(content).hexdigest() != expected:
            raise ValueError(f"measured source differs at {revision}: {Path(path).name}")
