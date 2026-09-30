"""Reproducible offline classical study with append-only attempt records."""

from __future__ import annotations

import argparse
import gzip
import importlib.metadata
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

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
from pipeline.benchmark.data import load_dataset
from pipeline.benchmark.metrics import display
from pipeline.benchmark.runtime import metadata, peak_rss_mib
from pipeline.challengers.study import evaluate_candidates, prepare_candidates

CONFIG = ROOT / "docs/models/wp07/config.json"
STUDY_HASH = "d8f553ffdde0b1b667e93246bd11ddd9ea8ddab59338a5e3adf7d01d235d61c4"


def provenance(config: dict, study: dict) -> dict:
    result = metadata(config)
    extra = [
        *sorted((ROOT / "pipeline/challengers").glob("*.py")),
        *sorted((ROOT / "pipeline/tests").glob("test_challengers*.py")),
    ]
    result["code_files"].update({str(p.relative_to(ROOT)): file_hash(p) for p in extra})
    result["code_sha256"] = digest(result["code_files"])
    result["versions"].update({p: importlib.metadata.version(p) for p in ("xgboost", "scipy", "scikit-learn")})
    result.update(
        study_config_sha256=file_hash(CONFIG),
        study_semantic_sha256=digest(study),
        dataset_sha256=file_hash(BENCHMARK / "dataset.json"),
        split_sha256=file_hash(BENCHMARK / "splits.json"),
        config_sha256=file_hash(CONTRACT / "config.json"),
        protocol_sha256=file_hash(CONTRACT / "PROTOCOL.md"),
        lock_sha256=file_hash(CONTRACT / "lock.json"),
    )
    return result


def render(report: dict, hashes: dict, costs: dict, runtime: dict) -> str:
    lines = [
        "# WP07 champion/challenger scorecard",
        "",
        "Explored chronological reconstruction, 70 races per horizon. As-of coverage 0/70; "
        "as-of/prospective scores **N/A**. No model promoted. Incumbent comparison N/A (artifact unavailable).",
        "",
        "Development nominees selected by inner-tune loss before outer scoring: "
        + ", ".join(f"{h}: **{f}**" for h, f in report["selection"]["champions"].items())
        + ".",
        "",
        "| Horizon | Candidate | LL | Brier | ECE | MAE | Rho | Winner hit | "
        "Top3 | Top10 | Coverage | Paired block improvement CI |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for horizon, section in report["horizons"].items():
        for name, summary in section["baselines"].items():
            m = summary["metrics"]
            values = [
                display(m[k])
                for k in (
                    "winner_log_loss",
                    "winner_brier",
                    "ece",
                    "rank_mae",
                    "rank_correlation",
                    "winner_hit",
                    "top3_overlap",
                    "top10_overlap",
                )
            ]
            lines.append(
                f"| {horizon} | baseline:{name} | " + " | ".join(values) + f" | {display(summary['coverage'])} | N/A |"
            )
        for name, cell in section["candidates"].items():
            summary = cell["calibrated"]
            m = summary["metrics"]
            ci = cell["paired_vs_comparator"]["block"]["ci95"]
            values = [
                display(m[k])
                for k in (
                    "winner_log_loss",
                    "winner_brier",
                    "ece",
                    "rank_mae",
                    "rank_correlation",
                    "winner_hit",
                    "top3_overlap",
                    "top10_overlap",
                )
            ]
            interval = f"{ci[0]:.6f} to {ci[1]:.6f}" if ci else "N/A"
            lines.append(
                f"| {horizon} | {name} | " + " | ".join(values) + f" | {display(summary['coverage'])} | {interval} |"
            )
    inference = [v["inference_seconds_per_race"] for v in costs.values() if "inference_seconds_per_race" in v]
    lines += [
        "",
        "Positive improvement means comparator minus challenger. Fixed comparators: pre-weekend standings; "
        "post-qualifying qualifying. Both race and four-race paired intervals (2,000 draws), loss intervals, "
        "all baseline comparisons and ablation-vs-full pairs are in report.json.gz.",
        "",
        "Full JSON includes every prediction, cohort/target hash, denominator, reliability bin, fold and "
        "predeclared slice. Trials and model artifacts include fitting row hashes, optimizer diagnostics, "
        "selected configs, preprocessing and decoder powers.",
        "",
        "| Compute scope | Measurement |",
        "| --- | --- |",
        f"| Entire run (dataset, fitting, scoring, slices, serialization) | {runtime['elapsed_seconds']:.3f} s |",
        f"| Peak process RSS, includes all retained models | {runtime['peak_rss_mib']:.3f} MiB |",
        f"| Largest measured mean inference per race (model + decoder) | {max(inference):.6f} s |",
        f"| Attempted tuning fits | {sum('__trial' in k for k in costs)} |",
        "",
        "Local single-thread CPU experiment; timing is per-fold mean, "
        "not worst-race latency or deployment qualification. "
        "Runtime/costs are separate from semantic results. Prediction artifacts are additive and offline.",
        "",
        "Grid/weather/practice/tyre ablations N/A: absent from the frozen WP05 contract. "
        "Season pooling tests one regulation era only. Rare-entry slices are proxies, not verified reserve status. "
        "Four calibration races give weak calibration evidence. Negative and inconclusive outcomes remain retained.",
        "",
        "Promotion guardrails remain frozen: prospective/operational evidence and independent WP09 review are missing. "
        "No future-superiority claim follows from this diagnostic table.",
        "",
        "## Fingerprints",
        "",
    ]
    lines.extend(f"- {k}: `{v}`" for k, v in hashes.items())
    return "\n".join(lines) + "\n"


def run(output: Path) -> str:
    identifier = f"wp07-{uuid4().hex}"
    directory = output / "experiments" / identifier
    write_once(directory / "started.json", {"id": identifier, "status": "started", "at": datetime.now(UTC).isoformat()})
    start = time.perf_counter()
    try:
        verify_lock()
        if file_hash(CONFIG) != STUDY_HASH:
            raise ValueError("preregistered WP07 study config changed")
        config, study = read_json(CONTRACT / "config.json"), read_json(CONFIG)
        if study["seed"] != config["seed"] or study["decoder"]["initial_temperature"] != config["rank_temperature"]:
            raise ValueError("study differs from benchmark seed/initial decoder")
        run_metadata = provenance(config, study)
        write_once(directory / "prepared.json", run_metadata)
        with tempfile.TemporaryDirectory(prefix="gridoracle-wp07-") as scratch:
            frames, targets, dataset = load_dataset(Path(scratch))
        if dataset != read_json(BENCHMARK / "dataset.json"):
            raise ValueError("reconstructed dataset differs from frozen cohort")
        splits = read_json(BENCHMARK / "splits.json")
        prepared, costs, selection = prepare_candidates(frames, targets, dataset, splits, config, study, directory)
        report = evaluate_candidates(prepared, frames, targets, dataset, splits, config, study, costs, selection)
        report["fingerprints"] = {k: v for k, v in run_metadata.items() if k.endswith("sha256")}
        hashes = {**report["fingerprints"], "report_sha256": digest(report)}
        write_bytes_once(directory / "report.json.gz", gzip.compress(canonical(report), mtime=0))
        artifact_files = {str(p.relative_to(directory)): file_hash(p) for p in sorted((directory / "models").glob("*"))}
        runtime = {
            **run_metadata,
            **hashes,
            "experiment_id": identifier,
            "model_files": artifact_files,
            "model_bundle_sha256": digest(artifact_files),
            "costs": costs,
            "elapsed_seconds": time.perf_counter() - start,
            "peak_rss_mib": peak_rss_mib(),
        }
        write_once(directory / "run-manifest.json", runtime)
        write_bytes_once(directory / "report.md", render(report, hashes, costs, runtime).encode())
        write_once(
            directory / "finished.json",
            {
                "id": identifier,
                "status": "succeeded",
                "at": datetime.now(UTC).isoformat(),
                "result": hashes,
                "model_bundle_sha256": runtime["model_bundle_sha256"],
            },
        )
    except Exception as error:
        try:
            write_once(
                directory / "finished.json",
                {
                    "id": identifier,
                    "status": "failed",
                    "at": datetime.now(UTC).isoformat(),
                    "error": f"{type(error).__name__}: {error}",
                    "elapsed_seconds": time.perf_counter() - start,
                },
            )
        except Exception as recording_error:
            error.add_note(f"Completion recording failed: {recording_error}; started attempt retained")
        raise
    return identifier


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    identifier = run(args.output)
    print(args.output / "experiments" / identifier / "report.md")


if __name__ == "__main__":
    main()
