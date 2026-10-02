"""Bounded native, offline container import checks using WP13 immutable pins."""

import argparse
import json
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=180)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = json.loads(
        (ROOT / "docs/operations/wp13/evidence/release.json").read_text()
    )
    report = {
        "passed": False,
        "host": platform.machine(),
        "checks": [],
        "limits": "Pinned WP13 images only; no build, deployment, live provider, "
        "CUDA/MPS or performance qualification",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        native = run("docker", "info", "--format", "{{.Architecture}}").stdout.strip()
        expected = "arm64" if native in {"aarch64", "arm64"} else "amd64"
        for role in ("api", "worker"):
            image = receipt["images"][role]["pin"]
            run("docker", "pull", image)
            arch = run(
                "docker", "image", "inspect", image, "--format", "{{.Architecture}}"
            ).stdout.strip()
            assert arch == expected, "emulated execution is not native evidence"
            modules = (
                "import fastapi, psycopg2, sqlalchemy"
                if role == "api"
                else "import numpy,pandas,pyarrow,xgboost,fastf1; "
                "from pipeline.selection.interface import Baseline"
            )
            result = run(
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--memory",
                "768m",
                "--cpus",
                "1",
                "--pids-limit",
                "128",
                "--entrypoint",
                "python",
                image,
                "-c",
                modules + "; import os,platform; assert os.getuid()==10001; "
                "print(platform.machine())",
            )
            report["checks"].append(
                {
                    "role": role,
                    "pin": image,
                    "architecture": arch,
                    "runtime_architecture": result.stdout.strip(),
                    "passed": True,
                }
            )
        report["passed"] = True
    except Exception as error:
        report["error"] = str(error)
        if isinstance(error, subprocess.CalledProcessError):
            report["stderr"] = error.stderr[-4000:]
        raise
    finally:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
