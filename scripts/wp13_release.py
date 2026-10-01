"""Assemble tested per-platform images and publish an immutable promotion receipt."""

import argparse
import json
import os
import re
import subprocess


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True)


def inspect(image):
    manifest = json.loads(
        docker(
            "buildx", "imagetools", "inspect", "--format", "{{json .Manifest}}", image
        )
    )
    return manifest["digest"], manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", args.version):
        parser.error("release requires a version tag")
    receipt = {
        "format": "gridoracle-oci-release-v1",
        "version": args.version,
        "source_revision": os.environ["GITHUB_SHA"],
        "workflow_run": os.environ["GITHUB_RUN_ID"],
        "images": {},
    }
    for role in ("api", "worker", "frontend"):
        image = f"{os.environ['REGISTRY']}/gridoracle-{role}:{args.version}"
        exists = (
            subprocess.run(
                ["docker", "manifest", "inspect", image], capture_output=True
            ).returncode
            == 0
        )
        if exists:
            raise ValueError("refusing to replace released version: " + image)
        sources = []
        for arch in ("amd64", "arm64"):
            source = image + "-" + arch
            checksum, _ = inspect(source)
            sources.append(source + "@" + checksum)
        docker("buildx", "imagetools", "create", "--tag", image, *sources)
        checksum, manifest = inspect(image)
        platforms = sorted(
            f"{m['platform']['os']}/{m['platform']['architecture']}"
            for m in manifest["manifests"]
            if m["platform"]["os"] == "linux"
        )
        if platforms != ["linux/amd64", "linux/arm64"]:
            raise ValueError("released index lacks required architecture pair")
        receipt["images"][role] = {
            "pin": image + "@" + checksum,
            "platforms": platforms,
        }
    with open(args.output, "x") as output:
        output.write(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
