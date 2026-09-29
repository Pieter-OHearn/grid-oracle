"""Reproduce the review's descriptive F1 baselines (Python standard library).

Usage: python docs/evidence/baseline_audit.py --cache /tmp/gridoracle-jolpica
       python docs/evidence/baseline_audit.py --cache /tmp/gridoracle-jolpica --offline

Only public Jolpica results are read. Raw responses stay in the selected cache.
The output is descriptive: current historical records are not proof of what
was available at a historical forecast cutoff. No GridOracle model is fitted.
"""

import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen


def fetch(season, endpoint, cache, offline, manifest):
    offset = 0
    merged = {}
    rows_seen = 0
    while True:
        url = f"https://api.jolpi.ca/ergast/f1/{season}/{endpoint}/?limit=100&offset={offset}"
        path = cache / f"{season}-{endpoint}-{offset}.json"
        if not path.exists():
            if offline:
                raise FileNotFoundError(path)
            time.sleep(0.4)
            request = Request(url, headers={"User-Agent": "GridOracleReview/1.0"})
            with urlopen(request, timeout=45) as response:
                raw = response.read()
            json.loads(raw)  # validate before storing
            path.write_bytes(raw)
        raw = path.read_bytes()
        manifest.append({"url": url, "sha256": hashlib.sha256(raw).hexdigest()})
        data = json.loads(raw)["MRData"]
        key = "Results" if endpoint == "results" else "QualifyingResults"
        count = 0
        for race in data["RaceTable"]["Races"]:
            rid = int(race["round"])
            if rid not in merged:
                merged[rid] = {
                    "name": race["raceName"],
                    "date": race["date"],
                    "rows": [],
                }
            merged[rid]["rows"].extend(race[key])
            count += len(race[key])
        assert count, (season, endpoint, offset)
        rows_seen += count
        offset += int(data["limit"])
        if offset >= int(data["total"]):
            assert rows_seen == int(data["total"])
            break
    for race in merged.values():
        ids = [row["Driver"]["driverId"] for row in race["rows"]]
        assert len(ids) == len(set(ids)), (season, endpoint, race["name"])
    return merged


def metrics(order, actual):
    pred = {driver: i + 1 for i, driver in enumerate(order)}
    assert set(pred) == set(actual)
    n = len(actual)
    return {
        "mae": sum(abs(pred[d] - actual[d]) for d in pred) / n,
        "exact": sum(pred[d] == actual[d] for d in pred) / n,
        "winner": float(order[0] == min(actual, key=actual.get)),
        "top3_overlap": len(set(order[:3]) & {d for d, p in actual.items() if p <= 3})
        / 3,
        "top10_overlap": len(
            set(order[:10]) & {d for d, p in actual.items() if p <= 10}
        )
        / 10,
    }


def mean_metrics(items):
    return {
        key: round(sum(row[key] for row in items) / len(items), 6) for key in items[0]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name("baseline-summary.json")
    )
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    manifest, all_rows, summaries = [], [], []
    for season in range(2022, 2026):
        races = fetch(season, "results", args.cache, args.offline, manifest)
        qualifying = fetch(season, "qualifying", args.cache, args.offline, manifest)
        groups = defaultdict(list)
        skipped_qualifying, status_counts, rows_count = [], Counter(), 0
        for rid, race in sorted(races.items()):
            results = race["rows"]
            actual = {r["Driver"]["driverId"]: int(r["position"]) for r in results}
            rows_count += len(results)
            status_counts.update(r["status"] for r in results)
            # Pit-lane/no-grid (grid=0) goes last, ordered by stable driver ID.
            grid_order = [
                r["Driver"]["driverId"]
                for r in sorted(
                    results,
                    key=lambda r: (
                        int(r["grid"]) if int(r["grid"]) > 0 else 1000,
                        r["Driver"]["driverId"],
                    ),
                )
            ]
            grid_metrics = metrics(grid_order, actual)
            groups["final_grid"].append(grid_metrics)
            qrows = qualifying.get(rid, {}).get("rows", [])
            qmap = {r["Driver"]["driverId"]: int(r["position"]) for r in qrows}
            qmetrics = None
            # Keep every result entrant; skip the whole race if any lacks a Q rank.
            if set(actual) <= set(qmap):
                qorder = sorted(actual, key=lambda d: (qmap[d], d))
                qmetrics = metrics(qorder, actual)
                groups["qualifying_order"].append(qmetrics)
            else:
                skipped_qualifying.append(
                    {"round": rid, "missing_drivers": sorted(set(actual) - set(qmap))}
                )
            all_rows.append(
                {
                    "season": season,
                    "round": rid,
                    "race": race["name"],
                    "date": race["date"],
                    "entrants": len(actual),
                    "final_grid": grid_metrics,
                    "qualifying_order": qmetrics,
                }
            )
        summaries.append(
            {
                "season": season,
                "races": len(races),
                "result_rows": rows_count,
                "raw_status_counts": dict(sorted(status_counts.items())),
                "qualifying_excluded": skipped_qualifying,
                "baselines": {
                    name: {"races": len(values), **mean_metrics(values)}
                    for name, values in groups.items()
                },
            }
        )
        print(json.dumps(summaries[-1]), flush=True)
    output = {
        "retrieved_at": datetime.now(UTC).isoformat(),
        "method": (
            "Equal race weighting; all result entrants including retirements/DNS/DSQ; "
            "official position numeric order; final grid zero placed last; "
            "qualifying reranked among result entrants; ties by driver ID; "
            "historical corrected records, not as-of snapshots."
        ),
        "seasons": summaries,
        "overall": {
            name: {"races": len(values), **mean_metrics(values)}
            for name in ("final_grid", "qualifying_order")
            if (values := [row[name] for row in all_rows if row[name] is not None])
        },
        "race_metrics": all_rows,
        "sources": manifest,
    }
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output["overall"]), flush=True)


if __name__ == "__main__":
    main()
