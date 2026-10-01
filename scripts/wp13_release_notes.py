"""Generate GitHub changelog notes, including unmerged staging commits."""

import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

from scripts.wp13_release import image_notes, validate_version


def changelog(body: str, source: str, repository: str, start_tag: str = "") -> str:
    # GitHub lists merged PRs, but an unmerged staging range can contain only
    # the comparison link. Keep that link and list its actual commit changes.
    if any(line.startswith(("* ", "- ")) for line in body.splitlines()):
        return body
    if not start_tag:
        match = re.search(r"/compare/([^\s]+?)\.\.\.", body)
        start_tag = unquote(match[1]) if match else ""
    if start_tag:
        validate_version(start_tag)
    revision = f"{start_tag}..{source}" if start_tag else source
    log = subprocess.check_output(
        ["git", "log", "--format=%H%x09%s", revision, "--"], text=True
    )
    lines = ["## Changelog", ""]
    for entry in log.splitlines():
        commit, subject = entry.split("\t", 1)
        # Subjects are data, not Markdown/HTML supplied to the publisher.
        subject = subject.replace("&", "&amp;").replace("<", "&lt;")
        for char in ("\\", "`", "*", "_", "[", "]"):
            subject = subject.replace(char, "\\" + char)
        lines.append(
            f"- {subject} ([{commit[:7]}](https://github.com/{repository}/commit/{commit}))"
        )
    if not log.strip():
        lines.append("No source commits changed in this release range.")
    return "\n".join(lines) + "\n\n" + body


def generate(receipt: dict, repository: str, start_tag: str = "") -> str:
    version = receipt["version"]
    source = receipt["source_revision"]
    validate_version(version)
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("source must be a full commit SHA")
    if not start_tag:
        pages = json.loads(
            subprocess.check_output(
                [
                    "gh",
                    "api",
                    "--paginate",
                    "--slurp",
                    f"repos/{repository}/releases?per_page=100",
                ],
                text=True,
            )
        )
        # Failed/cancelled tag builds and draft releases cannot become the
        # changelog baseline. Use the most recent actually published release.
        start_tag = next(
            (
                item["tag_name"]
                for page in pages
                for item in page
                if not item["draft"]
                and item.get("published_at")
                and item["tag_name"] != version
            ),
            "",
        )
    command = [
        "gh",
        "api",
        f"repos/{repository}/releases/generate-notes",
        "--method",
        "POST",
        "-f",
        f"tag_name={version}",
        "-f",
        f"target_commitish={source}",
    ]
    if start_tag:
        validate_version(start_tag)
        if start_tag == version:
            raise ValueError("changelog baseline must precede this release")
        command += ["-f", f"previous_tag_name={start_tag}"]
    generated = json.loads(subprocess.check_output(command, text=True))["body"]
    return (
        image_notes(receipt, repository)
        + "\n"
        + changelog(generated, source, repository, start_tag)
        + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--start-tag", default="")
    args = parser.parse_args()
    args.output.write_text(
        generate(json.loads(args.receipt.read_text()), args.repository, args.start_tag)
    )


if __name__ == "__main__":
    main()
