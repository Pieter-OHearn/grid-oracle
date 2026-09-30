"""One-command offline reproduction with durable success/failure events."""

from __future__ import annotations

import argparse
import gzip
import tempfile
import time
from pathlib import Path

from pipeline.benchmark.artifacts import (
    BENCHMARK,
    CONTRACT,
    ROOT,
    canonical,
    digest,
    file_hash,
    read_json,
    verify_lock,
    write_bytes_once,
    write_once,
)
from pipeline.benchmark.audit import reproduce_audit
from pipeline.benchmark.data import load_dataset
from pipeline.benchmark.registry import Registry
from pipeline.benchmark.report import build_report, render
from pipeline.benchmark.runtime import metadata, peak_rss_mib
from pipeline.benchmark.splits import make_splits


def freeze() -> None:
    """Register v2 against unchanged v1 dataset/splits; refuse any overwrite."""
    with tempfile.TemporaryDirectory(prefix="gridoracle-wp06-freeze-") as scratch:
        _, _, dataset = load_dataset(Path(scratch))
    if dataset != read_json(BENCHMARK / "dataset.json") or make_splits(dataset) != read_json(BENCHMARK / "splits.json"):
        raise ValueError("v2 must preserve the registered dataset and split bytes")
    paths = [
        CONTRACT / "PROTOCOL.md",
        CONTRACT / "config.json",
        BENCHMARK / "dataset.json",
        BENCHMARK / "splits.json",
        ROOT / "uv.lock",
    ]
    write_once(
        CONTRACT / "lock.json",
        {
            "version": "wp06-v2",
            "protocol_commit": "6ae63cd",
            "files": {str(path.relative_to(ROOT)): file_hash(path) for path in paths},
        },
    )


def prepare(directory: Path) -> tuple[dict, dict, dict]:
    config = read_json(CONTRACT / "config.json")
    provenance = metadata(config)
    provenance.update(
        config_sha256=file_hash(CONTRACT / "config.json"),
        dataset_sha256=file_hash(BENCHMARK / "dataset.json"),
        split_sha256=file_hash(BENCHMARK / "splits.json"),
        protocol_sha256=file_hash(CONTRACT / "PROTOCOL.md"),
    )
    write_once(directory / "prepared.json", provenance)
    return config, provenance, verify_lock()


def reproduce(config: dict) -> tuple[dict, dict, dict]:
    with tempfile.TemporaryDirectory(prefix="gridoracle-wp06-run-") as scratch:
        scratch = Path(scratch)
        frames, targets, dataset = load_dataset(scratch / "dataset")
        splits = read_json(BENCHMARK / "splits.json")
        if dataset != read_json(BENCHMARK / "dataset.json") or splits != make_splits(dataset):
            raise ValueError("frozen dataset/splits differ from reconstructed inputs")
        audit = reproduce_audit(scratch)
        report = build_report(frames, targets, dataset, splits, config)
    report["descriptive_audit"] = audit
    return report, dataset, splits


def store_report(directory: Path, report: dict, provenance: dict, hashes: dict) -> None:
    write_bytes_once(directory / "report.json.gz", gzip.compress(canonical(report), mtime=0))
    write_once(directory / "run-manifest.json", provenance)
    write_bytes_once(directory / "report.md", render(report, hashes).encode())


def run(output: Path) -> str:
    registry = Registry(output / "experiments")
    # An attempt exists before config parsing, source hashes or dependency discovery.
    identifier = registry.start({"phase": "requested", "protocol_directory": str(CONTRACT.relative_to(ROOT))})
    directory = output / "experiments" / identifier
    start = time.perf_counter()
    try:
        config, provenance, lock = prepare(directory)
        report, dataset, splits = reproduce(config)
        hashes = {
            "dataset_sha256": digest(dataset),
            "split_sha256": digest(splits),
            "config_sha256": file_hash(CONTRACT / "config.json"),
            "protocol_sha256": lock["files"][str((CONTRACT / "PROTOCOL.md").relative_to(ROOT))],
            "report_sha256": digest(report),
            "code_sha256": provenance["code_sha256"],
        }
        provenance.update(
            **hashes,
            elapsed_seconds=time.perf_counter() - start,
            peak_rss_mib=peak_rss_mib(),
            experiment_id=identifier,
            compute_scope="Entire offline reproduction; includes dataset, audit, baseline inference and resampling.",
            inference_budget_verdict="N/A; isolated inference timing not measured; no promotion requested",
        )
        store_report(directory, report, provenance, hashes)
        registry.finish(identifier, result=hashes)
    except Exception as error:
        try:
            registry.finish(identifier, error=error, result={"elapsed_seconds": time.perf_counter() - start})
        except Exception as recording_error:
            error.add_note(f"Failed to record completion for {identifier}: {recording_error}; started event retained")
        raise
    return identifier


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--output", type=Path, default=Path("/tmp/gridoracle-wp06"))
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
        print("Registered write-once WP06 v2 lock")
    else:
        identifier = run(args.output)
        print(args.output / "experiments" / identifier / "report.md")


if __name__ == "__main__":
    main()
