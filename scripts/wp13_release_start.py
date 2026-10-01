"""Resolve one immutable release identity; create its tag after passing tests."""

import argparse
import os
import re
import subprocess
from pathlib import Path

from scripts.wp13_release import validate_version


def identity(event: str, ref: str, sha: str, version: str = "") -> dict[str, str]:
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("source must be a full commit SHA")
    if event == "workflow_dispatch":
        if ref != "refs/heads/main":
            raise ValueError("manual releases must run from main")
        validate_version(version)
        publish = "true"
    elif event == "push" and ref.startswith("refs/tags/"):
        version = ref.removeprefix("refs/tags/")
        validate_version(version)
        publish = "true"
    elif event == "pull_request":
        version, publish = "ci-" + sha, "false"
    else:
        raise ValueError("unsupported release event/ref")
    return {"version": version, "source": sha, "publish": publish}


def create_tag(version: str, source: str) -> None:
    validate_version(version)
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("source must be a full commit SHA")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if head != source:
        raise ValueError("checkout differs from tested release source")
    ref = "refs/tags/" + version
    remote = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--tags", "origin", ref],
        capture_output=True,
        text=True,
    )
    if remote.returncode == 0:
        raise ValueError("refusing an existing remote release tag")
    if remote.returncode != 2:
        raise RuntimeError("unable to check remote release tag")
    if subprocess.run(["git", "show-ref", "--verify", "--quiet", ref]).returncode == 0:
        raise ValueError("refusing an existing local release tag")
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=github-actions[bot]",
            "-c",
            "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "tag",
            "-a",
            version,
            source,
            "-m",
            f"GridOracle {version}",
        ],
        check=True,
    )
    # Never force-push; a concurrent tag creator causes a hard failure.
    subprocess.run(["git", "push", "origin", f"{ref}:{ref}"], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "create-tag"))
    args = parser.parse_args()
    if args.action == "create-tag":
        create_tag(os.environ["RELEASE_VERSION"], os.environ["RELEASE_SOURCE"])
        return
    values = identity(
        os.environ["GITHUB_EVENT_NAME"],
        os.environ["GITHUB_REF"],
        os.environ["GITHUB_SHA"],
        os.getenv("INPUT_VERSION", ""),
    )
    previous = os.getenv("NOTES_START_TAG", "")
    if previous:
        validate_version(previous)
        if previous == values["version"]:
            raise ValueError("changelog baseline must precede this release")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        for key, value in values.items():
            output.write(f"{key}={value}\n")


if __name__ == "__main__":
    main()
