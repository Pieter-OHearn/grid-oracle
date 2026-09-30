"""Verify retained WP09 runs, fingerprints and identical final reproductions."""

import gzip
import json
import subprocess
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOCS = Path(__file__).parent


def hashed(path):
    return sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def verify():
    retained = json.loads((DOCS / "retention.json").read_text())
    for name, expected in retained["files"].items():
        if hashed(DOCS / name) != expected:
            raise ValueError(f"retained artifact drift: {name}")
    current = []
    for path in sorted((DOCS / "runs").glob("wp09-*")):
        manifest = json.loads((path / "manifest.json").read_text())
        finish = json.loads((path / "finished.json").read_text())
        for name, expected in finish["artifacts"].items():
            if hashed(path / name) != expected:
                raise ValueError(f"run artifact drift: {path.name}/{name}")
        report = json.loads(gzip.decompress((path / "report.json.gz").read_bytes()))
        if sha256(canonical(report)).hexdigest() != finish["report_sha256"]:
            raise ValueError(f"semantic report drift: {path.name}")
        if not manifest["git_dirty"]:
            for name, expected in manifest["code_files"].items():
                source = subprocess.check_output(
                    ["git", "show", f"{manifest['git_revision']}:{name}"], cwd=ROOT
                )
                if sha256(source).hexdigest() != expected:
                    raise ValueError(f"measured source drift: {path.name}/{name}")
        if path.name in retained["final_runs"]:
            if manifest["git_dirty"]:
                raise ValueError("final source was dirty")
            for name, expected in manifest["code_files"].items():
                if hashed(ROOT / name) != expected:
                    raise ValueError(f"current source drift: {name}")
            current.append(finish["report_sha256"])
    if len(current) != 2 or len(set(current)) != 1:
        raise ValueError("two identical final clean reports required")
    print(
        f"Verified {len(retained['files'])} files; two final reports reproduce {current[0]}"
    )


if __name__ == "__main__":
    verify()
