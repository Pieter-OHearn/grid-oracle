"""Release identity, immutable tag creation and public package metadata."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import wp13_release as release
from scripts.wp13_release_start import create_tag, identity

SHA = "a" * 40


@pytest.mark.parametrize("version", ["v1.2.3", "v0.1.0-wp13.5", "v1.0.0-rc.1"])
def test_shared_version_accepts_stable_and_prerelease(version):
    assert identity("workflow_dispatch", "refs/heads/main", SHA, version) == {
        "version": version,
        "source": SHA,
        "publish": "true",
    }
    assert identity("push", "refs/tags/" + version, SHA)["version"] == version


@pytest.mark.parametrize(
    "version",
    [
        "1.2.3",
        "v01.2.3",
        "v1.2.3-01",
        "v1.2.3-rc..1",
        "v1.2.3+build",
        "v1.2.3\nmalicious",
        "v1.2.3/other",
    ],
)
def test_invalid_versions_are_rejected_before_tagging(version):
    with pytest.raises(ValueError):
        identity("workflow_dispatch", "refs/heads/main", SHA, version)


def test_manual_releases_require_main_and_prs_never_publish():
    with pytest.raises(ValueError, match="main"):
        identity("workflow_dispatch", "refs/heads/feature/wp13", SHA, "v1.2.3")
    assert identity("pull_request", "refs/pull/108/merge", SHA)["publish"] == "false"
    with pytest.raises(ValueError, match="full commit"):
        identity("workflow_dispatch", "refs/heads/main", "main", "v1.2.3")
    with pytest.raises(ValueError, match="unsupported"):
        identity("push", "refs/heads/main", SHA)


def test_tag_creation_pushes_exact_tested_commit_and_refuses_reuse(
    tmp_path, monkeypatch
):
    remote = tmp_path / "origin.git"
    work = tmp_path / "checkout"
    subprocess.run(
        ["git", "init", "--bare", str(remote)], check=True, capture_output=True
    )
    subprocess.run(["git", "init", str(work)], check=True, capture_output=True)
    monkeypatch.chdir(work)
    Path("file").write_text("release fixture")
    subprocess.run(["git", "add", "file"], check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            "fixture",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "remote", "add", "origin", str(remote)], check=True)
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    with pytest.raises(ValueError, match="differs from tested"):
        create_tag("v1.2.3", SHA)
    create_tag("v1.2.3", source)
    actual = subprocess.check_output(
        ["git", "--git-dir", str(remote), "rev-parse", "v1.2.3^{commit}"], text=True
    ).strip()
    assert actual == source
    assert (
        subprocess.check_output(["git", "cat-file", "-t", "v1.2.3"], text=True).strip()
        == "tag"
    )
    with pytest.raises(ValueError, match="existing remote"):
        create_tag("v1.2.3", source)


def test_unreachable_remote_fails_without_creating_tag(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: SHA)
    run = Mock(return_value=Mock(returncode=128))
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(RuntimeError, match="unable to check remote"):
        create_tag("v1.2.3", SHA)
    assert run.call_count == 1


def test_release_annotates_both_architectures_and_writes_image_notes(
    tmp_path, monkeypatch
):
    calls = []
    monkeypatch.setenv("REGISTRY", "ghcr.io/fixture")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    monkeypatch.setenv("RELEASE_SOURCE", "b" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_REPOSITORY", "fixture/grid-oracle")
    monkeypatch.setattr(release.subprocess, "run", lambda *a, **k: Mock(returncode=1))
    monkeypatch.setattr(release, "docker", lambda *args: calls.append(args))

    def inspect(image):
        role = image.split("gridoracle-")[1].split(":")[0]
        return "sha256:" + SHA, {
            "annotations": {
                "org.opencontainers.image.description": release.DESCRIPTIONS[role]
            },
            "manifests": [
                {"platform": {"os": "linux", "architecture": arch}}
                for arch in ["amd64", "arm64"]
            ],
        }

    monkeypatch.setattr(release, "inspect", inspect)
    receipt, notes = tmp_path / "release.json", tmp_path / "notes.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "release",
            "--version",
            "v1.2.3",
            "--output",
            str(receipt),
            "--notes-output",
            str(notes),
        ],
    )
    release.main()
    value = json.loads(receipt.read_text())
    assert value["source_revision"] == "b" * 40
    assert len(calls) == 3
    for call, (role, image) in zip(calls, value["images"].items(), strict=True):
        assert (
            f"index:org.opencontainers.image.description={release.DESCRIPTIONS[role]}"
            in call
        )
        assert any("-amd64@sha256:" in item for item in call)
        assert any("-arm64@sha256:" in item for item in call)
        assert image["pin"] in notes.read_text()
        assert (
            f"https://github.com/fixture/grid-oracle/pkgs/container/gridoracle-{role}"
            in notes.read_text()
        )


def test_release_refuses_index_without_description(tmp_path, monkeypatch):
    monkeypatch.setenv("REGISTRY", "ghcr.io/fixture")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_REPOSITORY", "fixture/grid-oracle")
    monkeypatch.setattr(release.subprocess, "run", lambda *a, **k: Mock(returncode=1))
    monkeypatch.setattr(release, "docker", Mock())
    monkeypatch.setattr(release, "inspect", lambda _: ("sha256:" + SHA, {}))
    monkeypatch.setattr(
        "sys.argv",
        ["release", "--version", "v1.2.3", "--output", str(tmp_path / "receipt")],
    )
    with pytest.raises(ValueError, match="package description"):
        release.main()


def test_staging_changelog_lists_real_commits_and_preserves_compare_link(
    tmp_path, monkeypatch
):
    from scripts.wp13_release_notes import changelog

    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    monkeypatch.chdir(tmp_path)
    Path("file").write_text("old")
    subprocess.run(["git", "add", "file"], check=True)
    base = [
        "git",
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
    ]
    subprocess.run([*base, "previous"], check=True, capture_output=True)
    subprocess.run(["git", "tag", "v1.2.2"], check=True)
    Path("file").write_text("new")
    subprocess.run(["git", "add", "file"], check=True)
    subprocess.run(
        [*base, "feat(ops): add descriptions [staging]"],
        check=True,
        capture_output=True,
    )
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    comparison = (
        "**Full Changelog**: https://github.com/fixture/repo/compare/v1.2.2...v1.2.3"
    )
    notes = changelog(comparison, source, "fixture/repo")
    assert "add descriptions \\[staging\\]" in notes
    assert "previous" not in notes
    assert f"https://github.com/fixture/repo/commit/{source}" in notes
    assert comparison in notes


def test_merged_pr_changelog_is_preserved_without_duplicate_commit_list(monkeypatch):
    from scripts.wp13_release_notes import changelog

    git = Mock()
    monkeypatch.setattr(subprocess, "check_output", git)
    body = (
        "## What's Changed\n* Fix recovery by @owner in #108\n\n**Full Changelog**: URL"
    )
    assert changelog(body, SHA, "fixture/repo") == body
    git.assert_not_called()
