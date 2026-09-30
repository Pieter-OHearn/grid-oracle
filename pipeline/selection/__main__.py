"""Run: python -m pipeline.selection --output /tmp/gridoracle-wp09."""

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
    CONTRACT,
    ROOT,
    canonical,
    digest,
    file_hash,
    read_json,
    write_bytes_once,
    write_once,
)
from pipeline.benchmark.data import load_dataset
from pipeline.benchmark.runtime import metadata, peak_rss_mib
from pipeline.selection.study import DOCS, run_comparison, verify_sources


def render(report):
    lines = [
        "# WP09 selection report",
        "",
        "Retain **standings** pre-weekend and **qualifying** post-qualifying. No challenger is promoted.",
        "No deployed incumbent artifact was supplied; existing serving is unchanged. These are fixed fallback",
        "recommendations, not a claim of prospective baseline qualification or a publication instruction.",
        "",
        "All scores below are exploratory chronological reconstruction of 70 races per horizon.",
        "As-of eligibility: **0/70**. Prospective metrics: **N/A**, enrollment pending. Shadow races: **0**.",
        "Frozen WP06 v2 metrics, cohorts, tolerances and seeds are unchanged. All 75 retained selected",
        "model artifacts and calibration choices were replayed before comparison. Full JSON includes every",
        "prediction, baseline/contender paired race/block interval, raw/calibrated score, slice and failure.",
        "",
        "| Horizon | Model | Winner LL | Raw LL | Brier | ECE | Rank MAE | Rho | Hit | Top3 | Top10 | Gate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for h, section in report["horizons"].items():
        for name, cell in section["candidates"].items():
            m = cell["summary"]["metrics"]
            raw = cell["raw_summary"]["metrics"]["winner_log_loss"]
            values = [
                m["winner_log_loss"],
                raw,
                *[
                    m[k]
                    for k in (
                        "winner_brier",
                        "ece",
                        "rank_mae",
                        "rank_correlation",
                        "winner_hit",
                        "top3_overlap",
                        "top10_overlap",
                    )
                ],
            ]
            lines.append(f"| {h} | {name} | " + " | ".join(f"{v:.6f}" for v in values) + " | retain baseline |")
    lines += ["", "## Decisions and failures", ""]
    for h, section in report["horizons"].items():
        lines += [
            f"### {h}",
            "",
            f"Fixed fallback: `{section['retained']}`. "
            f"WP07 tune nominee remains `{section['decision']['wp07_tune_nominee']}`.",
            "",
        ]
        for name, cell in section["candidates"].items():
            if name.startswith("baseline:") or ("__" in name and not name.endswith("__full")):
                continue
            baseline = section["retained"].split(":")[1]
            comparison = cell["vs_baselines"][baseline]
            paired = comparison["paired"]["block"]
            reasons = comparison["diagnostic_guardrail_failures"]
            lines.append(
                f"- **{name}**: baseline minus candidate LL {paired['mean']:.6f}, "
                f"block CI {paired['ci95']}. Diagnostic guardrails: "
                + ("; ".join(reasons) if reasons else "pass on explored data only")
                + "."
            )
        lines += [
            "",
            "Every promotion gate fails: prospective and pre-outcome locking unverified; 0 races/blocks/shadows;",
            "no incumbent comparison or serving resource qualification; unresolved availability evidence. No",
            "candidate is selected by its best observed outer loss, and no ablation replaces the tune nominee.",
            "",
        ]
    lines += [
        "## Calibration and output limits",
        "",
        "Winner powers/temperatures are replayed exclusively on the four prior calibration races after fixed",
        "train+tune refits. They are out-of-sample relative to weights, but historical availability is unverified.",
        "The baseline keeps locked identity calibration. No new search, ensemble or outer-label calibration occurs.",
        "Winner-stratified PL suffix simulation preserves the winner marginal exactly and produces one coherent",
        "joint distribution. Conditional rank/top-k marginals are nested and sum to the fixed field's slot counts.",
        "They are not official podium/top-ten, points or retirement estimates; those outputs remain null.",
        "Conditional reliability uses fully classified fields only, with excluded races explicit. No such",
        "conditional output is approved for public display. Winner diagrams include all bin entry/race counts.",
        "Simulation standard errors describe Monte Carlo error, not uncertainty in the fitted model.",
        "",
        "## Promotion and rollback",
        "",
        "The local ledger requires explicit registration, challenger state, independent named review of",
        "a gate-passing artifact bound to the current incumbent, then a separate manual promotion action.",
        "Rollback points to a previously selected champion for the same horizon; it never edits old runs.",
        "No production pointer or database was changed in this experiment. The report records retention only.",
        "",
        "WP06's prospective 2027-2028 window and >=40 races/10 blocks/6 shadows remain outstanding.",
        "The current small calibration blocks, explored history, unknown source timestamps, missing incumbent",
        "and absent censoring model limit all interpretations. CPU results do not qualify a deployment host.",
        "",
    ]
    return "\n".join(lines)


def diagrams(report, root):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for horizon, section in report["horizons"].items():
        cells = {k: v for k, v in section["candidates"].items() if "__" not in k or k.endswith("__full")}
        fig, axes = plt.subplots(3, 3, figsize=(15, 12), layout="constrained")
        for ax, (name, cell) in zip(axes.flat, cells.items()):
            bins = cell["reliability_with_counts"]["winner"]["bins"]
            ax.plot([0, 1], [0, 1], "--", color="0.7", linewidth=1)
            occupied = [b for b in bins if b["entries"]]
            ax.plot(
                [b["mean_probability"] for b in occupied], [b["observed_rate"] for b in occupied], "o-", color="#155f83"
            )
            for b in occupied:
                ax.annotate(
                    f"{b['entries']}/{b['races']}",
                    (b["mean_probability"], b["observed_rate"]),
                    xytext=(0, 7),
                    textcoords="offset points",
                    fontsize=7,
                )
            ax.set(
                xlim=(-0.03, 1.03),
                ylim=(-0.03, 1.1),
                title=name,
                xlabel="Mean predicted winner probability",
                ylabel="Observed winner rate",
            )
        for ax in list(axes.flat)[len(cells) :]:
            ax.set_visible(False)
        fig.suptitle(
            f"{horizon}: explored reconstruction, 70 races\n"
            "Labels = entrant count / contributing races per bin; equal-race weights",
            fontsize=15,
        )
        fig.savefig(root / f"reliability-{horizon}.png", dpi=140)
        plt.close(fig)


def run(output):
    directory = Path(output) / ("wp09-" + uuid4().hex)
    start = time.perf_counter()
    write_once(directory / "started.json", {"status": "started", "at": datetime.now(UTC).isoformat()})
    try:
        inputs = verify_sources()
        config = read_json(CONTRACT / "config.json")
        manifest = metadata(config)
        manifest["code_files"].update(
            {str(p.relative_to(ROOT)): file_hash(p) for p in sorted((ROOT / "pipeline/selection").glob("*.py"))}
        )
        manifest["code_files"]["pipeline/tests/test_selection.py"] = file_hash(
            ROOT / "pipeline/tests/test_selection.py"
        )
        manifest["code_sha256"] = digest(manifest["code_files"])
        manifest["versions"].update(
            {p: importlib.metadata.version(p) for p in ("torch", "xgboost", "scipy", "matplotlib")}
        )
        manifest["input_lock_sha256"] = file_hash(DOCS / "input-lock.json")
        manifest["policy_sha256"] = file_hash(DOCS / "policy.json")
        manifest["retained_inputs"] = inputs
        write_once(directory / "manifest.json", manifest)
        with tempfile.TemporaryDirectory(prefix="wp09-data-") as scratch:
            frames, targets, dataset = load_dataset(Path(scratch))
        report = run_comparison(frames, targets, dataset, read_json(ROOT / "docs/benchmark/splits.json"))
        write_bytes_once(directory / "report.json.gz", gzip.compress(canonical(report), mtime=0))
        write_bytes_once(directory / "REPORT.md", render(report).encode())
        decisions = {h: s["decision"] for h, s in report["horizons"].items()}
        write_once(
            directory / "promotion-record.json",
            {
                "decisions": decisions,
                "report_sha256": digest(report),
                "publication_changed": False,
                "rollback": "no pointer changed; retain incumbent/fixed baseline",
            },
        )
        diagrams(report, directory)
        for name, expected in manifest["code_files"].items():
            if file_hash(ROOT / name) != expected:
                raise ValueError("source changed during experiment")
        write_once(
            directory / "finished.json",
            {
                "status": "succeeded",
                "elapsed_seconds": time.perf_counter() - start,
                "peak_rss_mib": peak_rss_mib(),
                "report_sha256": digest(report),
                "artifacts": {p.name: file_hash(p) for p in sorted(directory.iterdir()) if p.is_file()},
            },
        )
        return directory
    except BaseException as error:
        write_once(
            directory / "failed.json",
            {
                "status": "failed",
                "error": f"{type(error).__name__}: {error}",
                "elapsed_seconds": time.perf_counter() - start,
            },
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(run(args.output))


if __name__ == "__main__":
    main()
