"""Verify retained WP08 run events, model archives and clean-source fingerprints."""

import gzip
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def verify(root=Path(__file__).parent):
    count = 0
    semantic_hashes = []
    for run in sorted((root / "runs").glob("wp08-*")):
        retention = json.loads((run / "retention.json").read_text())
        for name, expected in retention["files"].items():
            assert hash_bytes((run / name).read_bytes()) == expected, (run.name, name)
        finish = run / "finished.json"
        if finish.exists():
            finished = json.loads(finish.read_text())
            with tarfile.open(run / "checkpoints.tar.gz") as archive:
                for name, expected in finished["artifacts"].items():
                    content = (
                        archive.extractfile(name).read()
                        if name.startswith("checkpoints/")
                        else (run / name).read_bytes()
                    )
                    assert hash_bytes(content) == expected, (run.name, name)
            value = json.loads(gzip.decompress((run / "report.json.gz").read_bytes()))
            canonical = (
                json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
            ).encode()
            assert hash_bytes(canonical) == finished["result_sha256"], run.name
            manifest = json.loads((run / "manifest.json").read_text())
            if not retention["development_only"]:
                assert not manifest["git_dirty"]
                for name, expected in manifest["code_files"].items():
                    content = subprocess.check_output(
                        ["git", "show", f"{manifest['git_revision']}:{name}"]
                    )
                    assert hash_bytes(content) == expected, name
                    assert hash_bytes(Path(name).read_bytes()) == expected, (
                        "current source drift",
                        name,
                    )
                semantic_hashes.append(finished["result_sha256"])
        else:
            assert (run / "failed.json").exists(), run.name
        count += 1
    assert len(semantic_hashes) >= 2 and len(set(semantic_hashes)) == 1
    print(
        f"Verified {count} retained attempts; "
        f"clean-run semantic hash {semantic_hashes[0]}"
    )


if __name__ == "__main__":
    verify()
