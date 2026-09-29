"""One-command offline reproduction with durable success/failure events."""

from __future__ import annotations

import argparse
import gzip
import tempfile
import time
from pathlib import Path

from pipeline.benchmark.artifacts import (
    BENCHMARK,
    ROOT,
    canonical,
    digest,
    file_hash,
    read_json,
    verify_lock,
    write_once,
)
from pipeline.benchmark.audit import reproduce_audit
from pipeline.benchmark.data import load_dataset
from pipeline.benchmark.registry import Registry
from pipeline.benchmark.report import build_report, render
from pipeline.benchmark.runtime import metadata, peak_rss_mib
from pipeline.benchmark.splits import make_splits


def freeze() -> None:
    # Explicit registration action; existing files are never overwritten.
    with tempfile.TemporaryDirectory(prefix="gridoracle-wp06-freeze-") as scratch:
        _, _, dataset = load_dataset(Path(scratch))
    write_once(BENCHMARK / "dataset.json", dataset)
    write_once(BENCHMARK / "splits.json", make_splits(dataset))
    names = ["docs/benchmark/" + name for name in ("PROTOCOL.md", "config.json", "dataset.json", "splits.json")]
    names.append("uv.lock")
    write_once(
        BENCHMARK / "lock.json",
        {
            "version": "wp06-v1",
            "protocol_commit": "d4b75ed",
            "files": {name: file_hash(ROOT / name) for name in names},
        },
    )


def run(output: Path) -> str:
    config = read_json(BENCHMARK / "config.json")
    registry = Registry(output / "experiments")
    provenance = metadata(config)
    provenance.update(
        config_sha256=file_hash(BENCHMARK / "config.json"),
        dataset_sha256=file_hash(BENCHMARK / "dataset.json"),
        split_sha256=file_hash(BENCHMARK / "splits.json"),
        protocol_sha256=file_hash(BENCHMARK / "PROTOCOL.md"),
    )
    identifier = registry.start(provenance)
    directory = output / "experiments" / identifier
    start = time.perf_counter()
    try:
        lock = verify_lock()
        with tempfile.TemporaryDirectory(prefix="gridoracle-wp06-run-") as scratch:
            scratch = Path(scratch)
            frames, targets, dataset = load_dataset(scratch / "dataset")
            splits = read_json(BENCHMARK / "splits.json")
            if dataset != read_json(BENCHMARK / "dataset.json") or splits != make_splits(dataset):
                raise ValueError("frozen dataset/splits differ from reconstructed inputs")
            audit = reproduce_audit(scratch)
            report = build_report(frames, targets, dataset, splits, config)
        report["descriptive_audit"] = audit
        hashes = {
            "dataset_sha256": digest(dataset),
            "split_sha256": digest(splits),
            "config_sha256": file_hash(BENCHMARK / "config.json"),
            "protocol_sha256": lock["files"]["docs/benchmark/PROTOCOL.md"],
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
        with (directory / "report.json.gz").open("xb") as handle:
            handle.write(gzip.compress(canonical(report), mtime=0))
        write_once(directory / "run-manifest.json", provenance)
        (directory / "report.md").write_text(render(report, hashes))
        registry.finish(identifier, result=hashes)
    except Exception as error:
        registry.finish(
            identifier,
            error=error,
            result={"elapsed_seconds": time.perf_counter() - start, "peak_rss_mib": peak_rss_mib()},
        )
        raise
    return identifier


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--output", type=Path, default=Path("/tmp/gridoracle-wp06"))
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
        print("Registered write-once WP06 manifests")
    else:
        identifier = run(args.output)
        print(args.output / "experiments" / identifier / "report.md")


if __name__ == "__main__":
    main()
