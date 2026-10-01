"""Known defects must cause assertion failures, never skip/collection errors."""

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MUTATIONS = {
    "partial-publication": "test_partial_publish_keeps_last_good",
    "future-availability": "test_future_availability_is_rejected",
    "tie-advantage": "test_season_opening_ties_never_favor_identity",
    "unchecked-output-hash": "test_corrupt_stored_output_hash_is_rejected",
    "future-live-qualifying": (
        "test_future_sources_results_and_newer_model_cannot_change_issued_forecast"
    ),
    "recaptured-snapshot": (
        "test_feature_retry_reuses_partially_committed_observation[post_qualifying]"
    ),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not os.getenv("WP14_POSTGRES_URL"):
        parser.error("WP14_POSTGRES_URL is required; skipped tests cannot kill mutants")
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"passed": False, "mutations": []}
    try:
        for name, test in MUTATIONS.items():
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    f"scripts/tests/test_wp14_postgres.py::{test}",
                    "-q",
                    f"--junitxml={args.output / (name + '.xml')}",
                ],
                env={**os.environ, "WP14_MUTANT": name},
                capture_output=True,
                text=True,
                timeout=120,
            )
            (args.output / (name + ".log")).write_text(result.stdout + result.stderr)
            suite = ET.parse(args.output / (name + ".xml"))
            cases = list(suite.iter("testcase"))
            killed = (
                result.returncode == 1
                and len(cases) == 1
                and len(list(suite.iter("failure"))) == 1
                and not list(suite.iter("error"))
                and not list(suite.iter("skipped"))
            )
            report["mutations"].append(
                {
                    "name": name,
                    "test": test,
                    "killed": killed,
                    "exit_code": result.returncode,
                }
            )
            if not killed:
                raise AssertionError(
                    f"mutation survived or test infrastructure failed: {name}"
                )
        report["passed"] = True
    finally:
        (args.output / "mutations.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
