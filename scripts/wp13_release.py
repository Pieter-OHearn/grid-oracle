"""Assemble tested per-platform images and publish an immutable promotion receipt."""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

DESCRIPTIONS = {
    "api": (
        "GridOracle backend API serving published Formula 1 forecasts and provenance."
    ),
    "worker": "GridOracle background worker and scheduler for bounded forecast jobs.",
    "frontend": (
        "GridOracle web dashboard for Formula 1 forecasts, results and provenance."
    ),
}


def validate_version(version: str) -> None:
    number = r"(?:0|[1-9][0-9]*)"
    pattern = rf"v{number}\.{number}\.{number}(?:-[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*)?"
    if len(version) > 120 or not re.fullmatch(pattern, version):
        raise ValueError("release requires vMAJOR.MINOR.PATCH with optional prerelease")
    if "-" in version:
        for part in version.split("-", 1)[1].split("."):
            if part.isdecimal() and len(part) > 1 and part.startswith("0"):
                raise ValueError(
                    "numeric prerelease identifiers cannot have leading zeros"
                )


def image_notes(receipt: dict, repository: str) -> str:
    lines = [
        "## GridOracle runtime images",
        "",
        f"Version: `{receipt['version']}` · "
        f"[Source commit](https://github.com/{repository}/commit/"
        f"{receipt['source_revision']})",
        "",
        "All images support **linux/amd64** and **linux/arm64**.",
        "",
        "| Component | Description | Immutable image |",
        "| --- | --- | --- |",
    ]
    for role, image in receipt["images"].items():
        url = f"https://github.com/{repository}/pkgs/container/gridoracle-{role}"
        lines.append(f"| [{role}]({url}) | {DESCRIPTIONS[role]} | `{image['pin']}` |")
    lines += [
        "",
        "The attached `release.json` records exact image digests, source revision,",
        "architectures and workflow run. Promote its version@digest pins through a",
        "reviewed homelab PR. This release performs no deployment.",
        "",
    ]
    return "\n".join(lines)


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True)


def inspect(image):
    summary = json.loads(
        docker(
            "buildx", "imagetools", "inspect", "--format", "{{json .Manifest}}", image
        )
    )
    manifest = json.loads(docker("buildx", "imagetools", "inspect", "--raw", image))
    return summary["digest"], manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--notes-output")
    args = parser.parse_args()
    validate_version(args.version)
    receipt = {
        "format": "gridoracle-oci-release-v1",
        "version": args.version,
        "source_revision": os.getenv("RELEASE_SOURCE") or os.environ["GITHUB_SHA"],
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
            checksum, source_manifest = inspect(source)
            if source_manifest.get("mediaType") not in (
                "application/vnd.oci.image.manifest.v1+json",
                "application/vnd.oci.image.index.v1+json",
            ):
                raise ValueError("description annotations require OCI source images")
            sources.append(source + "@" + checksum)
        docker(
            "buildx",
            "imagetools",
            "create",
            "--tag",
            image,
            "--annotation",
            f"index:org.opencontainers.image.description={DESCRIPTIONS[role]}",
            "--annotation",
            f"index:org.opencontainers.image.source=https://github.com/{os.environ['GITHUB_REPOSITORY']}",
            "--annotation",
            f"index:org.opencontainers.image.version={args.version}",
            "--annotation",
            f"index:org.opencontainers.image.revision={receipt['source_revision']}",
            *sources,
        )
        checksum, manifest = inspect(image)
        if (
            manifest.get("annotations", {}).get("org.opencontainers.image.description")
            != DESCRIPTIONS[role]
        ):
            raise ValueError("released index lacks its package description")
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
    if args.notes_output:
        Path(args.notes_output).write_text(
            image_notes(receipt, os.environ["GITHUB_REPOSITORY"])
        )


if __name__ == "__main__":
    main()
