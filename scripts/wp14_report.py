"""Fail-closed regression coverage receipt; never equate skips with acceptance."""

import argparse
import json
import platform
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from gridoracle.ops.bundle import file_digest
from scripts.regression.replay import ROOT, checked_fixtures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _, lineage = checked_fixtures()
    report = {
        "passed": False,
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "source_sha256": {
            str(path.relative_to(ROOT)): file_digest(path)
            for path in [
                ROOT / "scripts/regression/replay.py",
                ROOT / "scripts/tests/test_wp14_postgres.py",
                *sorted((ROOT / "scripts").glob("wp14_*")),
            ]
            if path.is_file()
        },
        "fixture_lineage": lineage,
        "limits": [
            "Synthetic test adapter; production feature/predict/publish/evaluate "
            "adapters remain blocked. No production bundle or promotion claim.",
            "Fixed retained baselines execute; retained XGBoost weights load "
            "offline on frozen historical features, without refit or selection.",
            "Recorded Jolpica contracts only; no current terms, provider uptime, "
            "FastF1/F1 live protocol or actual source publication-time claim.",
            "Native AMD64/ARM64 CPU runners and pinned WP13 containers only; "
            "no CUDA/MPS, physical Pi load, off-disk transfer or public deployment.",
            "Chromium/axe automation only; native screen reader, real devices, "
            "human usability and public ingress remain release checks.",
            "Tiny bounded fixture proves lifecycle/storage integrity, not "
            "forecast accuracy, prospective quality, production RPO/RTO or SLOs.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        suite = ET.parse(args.junit)
        report["tests"] = len(list(suite.iter("testcase")))
        report["failures"] = len(list(suite.iter("failure")))
        report["errors"] = len(list(suite.iter("error")))
        report["skips"] = len(list(suite.iter("skipped")))
        assert report["tests"] >= 39, (
            "missing lifecycle and committed-write retry cases"
        )
        assert not any(report[k] for k in ("failures", "errors", "skips"))
        report["passed"] = True
    finally:
        args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
