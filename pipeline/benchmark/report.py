"""Diagnostic scorecards with explicit unavailable as-of/prospective sections."""

from __future__ import annotations

from itertools import combinations

from pipeline.benchmark.baselines import predict
from pipeline.benchmark.evaluation import evaluate_predictions
from pipeline.benchmark.metrics import aggregate, display
from pipeline.benchmark.splits import validate_splits
from pipeline.benchmark.temporal import validate_features
from pipeline.benchmark.uncertainty import uncertainty


def slice_tags(race: dict, frame, targets: list[dict]) -> list[str]:
    return [
        f"season:{race['season']}",
        "era:2022-2025_regulation_cohort",
        f"circuit:{race['circuit']}",
        f"field_size:{len(race['drivers'])}",
        f"missing_history:{bool(frame.missing__history.any())}",
        f"missing_qualifying:{bool(frame.missing__qualifying.any())}",
        "weather:unavailable",
        *[f"driver:{d}" for d in race["drivers"]],
        *[f"team:{t}" for t in sorted({r["team"] for r in targets})],
    ]


def score_baseline(
    name: str, horizon: str, frames: dict, targets: dict, dataset: dict, splits: dict, config: dict
) -> list:
    predictions, annotations = {}, {}
    races = {r["race"]: r for r in dataset["races"]}
    for fold in splits["folds"]:
        for key in fold["evaluation"]:
            frame = frames[horizon][frames[horizon].race_key == key]
            predictions[key] = predict(frame, name, horizon, config["rank_temperature"])
            annotations[key] = dict(
                slices=slice_tags(races[key], frame, targets[key]),
                missing_feature_cells=int(frame.isna().sum().sum()),
                missing_history_entries=int(frame.missing__history.sum()),
                missing_qualifying_entries=int(frame.missing__qualifying.sum()),
                prediction=predictions[key],
            )
    result = evaluate_predictions(predictions, targets, dataset, splits, config)
    return [{**row, **annotations[row["race"]]} for row in result["races"]]


def summarize(records: list[dict], expected: int, config: dict) -> dict:
    summary = aggregate(records, expected, config["calibration_bins"])
    summary["loss_uncertainty"] = uncertainty(records, config)
    summary["missing_features"] = sum(r["missing_feature_cells"] for r in records)
    summary["entries"] = sum(r["field_size"] for r in records)
    summary["ranking_excluded_entries"] = sum(r["field_size"] - r["classified_entries"] for r in records)
    return summary


def slice_report(records: list[dict], config: dict) -> dict:
    result = {}
    for tag in sorted({tag for row in records for tag in row["slices"]}):
        subset = [r for r in records if tag in r["slices"]]
        cell = summarize(subset, len(subset), config)
        cell["interpretation"] = "small descriptive slice" if len(subset) < 10 else "descriptive; overlapping slices"
        result[tag] = cell
    return result


def build_report(frames: dict, targets: dict, dataset: dict, splits: dict, config: dict) -> dict:
    validate_splits(splits, dataset)
    expected = sum(len(f["evaluation"]) for f in splits["folds"])
    result = {
        "protocol": config["protocol_version"],
        "interpretation": "explored reconstruction; no model-promotion claims",
        "exploratory": {},
        "asof": {
            **aggregate([], expected, config["calibration_bins"]),
            "reason": "All WP05 entries have unverified historical source/entry availability.",
            "excluded_races": [r for f in splits["folds"] for r in f["evaluation"]],
        },
        "prospective": {
            **aggregate([], 0, config["calibration_bins"]),
            "reason": "2027-2028 calendars and prospective predictions are not yet enrolled.",
        },
        "promotion": {"promoted": False, "reason": "No eligible prospective evidence; independent review mandatory."},
    }
    for horizon, names in config["baselines"].items():
        validate_features(frames[horizon], horizon)
        cells, records = {}, {}
        for name in names:
            records[name] = score_baseline(name, horizon, frames, targets, dataset, splits, config)
            cells[name] = {
                "probabilistic": summarize(records[name], expected, config),
                "deterministic": deterministic_summary(records[name], expected, config),
                "folds": {
                    f["id"]: summarize([r for r in records[name] if r["fold"] == f["id"]], len(f["evaluation"]), config)
                    for f in splits["folds"]
                },
                "slices": slice_report(records[name], config),
                "races": records[name],
            }
        result["exploratory"][horizon] = {
            "baselines": cells,
            "paired_loss_improvement": {
                f"{reference}_minus_{candidate}": uncertainty(records[candidate], config, records[reference])
                for reference, candidate in combinations(names, 2)
            },
        }
    return result


def deterministic_summary(records: list[dict], expected: int, config: dict) -> dict:
    deterministic = [{**r, "winner_log_loss": None, "winner_brier": None, "reliability": []} for r in records]
    return aggregate(deterministic, expected, config["calibration_bins"])


def render(report: dict, hashes: dict) -> str:
    lines = [
        "# WP06 baseline report",
        "",
        "Exploratory chronological reconstruction of explored 2022-2025 history. No model-promotion claims.",
        "Deterministic orders and probability counterparts share the same WP02 targets and race cohorts.",
        "",
        "| Horizon | Baseline | Races | Winner log loss | Brier | ECE | Rank MAE | "
        "Podium overlap | Coverage | Block loss 95% CI |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for horizon, section in report["exploratory"].items():
        for name, cell in section["baselines"].items():
            summary = cell["probabilistic"]
            m = summary["metrics"]
            block = summary["loss_uncertainty"]["block"]
            ci = block["ci95"] if block else None
            interval = f"{ci[0]:.6f} to {ci[1]:.6f}" if ci else "N/A"
            lines.append(
                f"| {horizon} | {name} | {summary['predicted_races']} | {display(m['winner_log_loss'])} | "
                f"{display(m['winner_brier'])} | {display(m['ece'])} | {display(m['rank_mae'])} | "
                f"{display(m['top3_overlap'])} | {display(summary['coverage'])} | {interval} |"
            )
    lines.extend(
        [
            "",
            "Deterministic probability losses: **N/A** (orders do not assert probabilities).",
            "As-of winner log loss: **N/A**; **0 / 70** diagnostic outer races satisfy the as-of contract.",
            "Prospective winner log loss, coverage and uncertainty: **N/A** (enrollment pending).",
            "",
            "The compressed JSON report (`report.json.gz`) contains per-race predictions, target/cohort hashes,",
            "folds, metric denominators,",
            "calibration bins, missing-feature counts, excluded ranking entries, all paired race/block intervals,",
            "and circuit/season/era/driver/team/field-size/missingness slices. All entrants stay in winner fields.",
            "",
            "The separate descriptive audit reproduces 91 qualifying-order races and 92 grid-order races.",
            "Its provider numeric-order targets differ from this report; the figures cannot establish uplift.",
            "",
            "No fitted challenger or calibrator was trained. Baseline parameters and tolerances are preregistered.",
            "Unknown historical availability, reconstructed entry lists, race-only standings and weather absence",
            "limit this report to diagnostics. Small and overlapping slices cannot justify promotion.",
            "",
            "## Reproduce",
            "",
            "```sh",
            "UV_CACHE_DIR=/tmp/gridoracle-uv-cache uv run --offline --frozen --extra pipeline --group dev \\",
            "  python -m pipeline.benchmark run --output /tmp/gridoracle-wp06",
            "```",
            "",
            "Every attempt gets a new append-only experiment directory; compare semantic report hashes.",
            "",
            "## Artifact hashes",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in hashes.items())
    return "\n".join(lines) + "\n"
