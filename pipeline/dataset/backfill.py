"""Offline CLI for resumable audited historical dataset reconstruction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.dataset.historical import reconstruct_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstruct a versioned audited dataset from raw snapshots.")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--season",
        type=int,
        action="append",
        dest="seasons",
        help="Repeat to resume only selected season partitions.",
    )
    args = parser.parse_args()
    result = reconstruct_dataset(args.archive, args.output, seasons=args.seasons)
    print(json.dumps({"root": result["root"], "manifest_sha256": result["manifest_sha256"]}))


if __name__ == "__main__":
    main()
