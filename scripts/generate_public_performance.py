"""Allowlist a pinned stored WP09 report for public serving; never rescore it."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from api.schemas.public import HistoricalPerformance
from api.services.trust import metric_projection

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = "wp09-862243fc69d04f5ab9967b8499ca19da"
REPORT = ROOT / "docs/models/wp09/runs" / EVIDENCE / "report.json.gz"
# Final measured source c719c85; matching semantic reports were independently retained.
SEMANTIC_SHA256 = "e1c5d0fd6b002e48a10a428b27f64348b72be217cd86e97720d4a9cc4d9c99c7"
OUTPUT = ROOT / "api/data/historical-performance.json"


def projection():
    report = json.loads(gzip.decompress(REPORT.read_bytes()))
    canonical = (
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()
    if hashlib.sha256(canonical).hexdigest() != SEMANTIC_SHA256:
        raise ValueError("Stored WP09 report hash differs from reviewed evidence")
    candidates = []
    names = {
        "baseline:uniform": "Uniform baseline",
        "baseline:standings": "Race-only standings baseline",
        "baseline:recent_form": "Recent classified form baseline",
        "baseline:qualifying": "Qualifying-order baseline",
        "hierarchical_pl": "Hierarchical Plackett-Luce",
        "xgb_ranking": "Boosted ranking",
        "xgb_regression": "Boosted regression",
        "wp08_reference": "Custom linear reference",
        "wp08_nonlinear": "Custom nonlinear model",
    }
    for horizon, group in report["horizons"].items():
        for key, candidate in group["candidates"].items():
            # Every variant and poor race retained, with fixed source ordering.
            family, _, variant = key.partition("__")
            name = names[family] + (
                " · " + variant.replace("_", " ") if variant else ""
            )
            summary = candidate["summary"]
            counts = dict(summary["metric_race_counts"])
            counts["ece"] = counts["winner_log_loss"]
            races = []
            for record in candidate["races"]:
                season, round_number = map(int, record["race"].split(":"))
                races.append(
                    dict(
                        season=season,
                        round=round_number,
                        missing_reason=None,
                        field_entries=record["field_size"],
                        classified_entries=record["classified_entries"],
                        missing_feature_cells=record["missing_feature_cells"],
                        **{
                            metric: record[metric]
                            for metric in (
                                "winner_log_loss",
                                "winner_hit",
                                "top3_overlap",
                                "top10_overlap",
                                "rank_mae",
                            )
                        },
                    )
                )
            for missing in candidate["missing"]:
                season, round_number = map(int, missing["race"].split(":"))
                # Reason is controlled public copy, never research exception text.
                races.append(
                    dict(
                        season=season,
                        round=round_number,
                        missing_reason="No prediction supplied",
                        field_entries=None,
                        classified_entries=None,
                        missing_feature_cells=None,
                        **{
                            metric: None
                            for metric in (
                                "winner_log_loss",
                                "winner_hit",
                                "top3_overlap",
                                "top10_overlap",
                                "rank_mae",
                            )
                        },
                    )
                )
            bins = [
                {
                    k: b[k]
                    for k in (
                        "lower",
                        "upper",
                        "mean_probability",
                        "observed_rate",
                        "entries",
                        "races",
                    )
                }
                for b in candidate["reliability_with_counts"]["winner"]["bins"]
            ]
            candidates.append(
                {
                    "name": name,
                    "horizon": horizon,
                    "retained": key == group["retained"],
                    "expected_races": summary["expected_races"],
                    "predicted_races": summary["predicted_races"],
                    "metrics": [
                        m.model_dump()
                        for m in metric_projection(summary["metrics"], counts)
                    ],
                    "winner_loss_interval": candidate["loss_uncertainty"]["block"][
                        "ci95"
                    ],
                    "races": sorted(races, key=lambda r: (r["season"], r["round"])),
                    "reliability": bins,
                }
            )
    return HistoricalPerformance(
        evidence_id=EVIDENCE,
        scope="explored_chronological_reconstruction",
        candidates=candidates,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = (
        json.dumps(
            projection().model_dump(), ensure_ascii=False, sort_keys=True, indent=2
        )
        + "\n"
    )
    if args.check:
        if OUTPUT.read_text() != content:
            raise SystemExit("Public performance projection drift")
    else:
        OUTPUT.parent.mkdir(exist_ok=True)
        OUTPUT.write_text(content)


if __name__ == "__main__":
    main()
