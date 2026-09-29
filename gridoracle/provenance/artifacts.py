"""Content-addressed artifact files used by immutable provenance manifests."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from tempfile import mkstemp
from typing import Final

_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_NAMESPACE_PART_RE: Final = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


class ArtifactIntegrityError(ValueError):
    """An artifact does not match its declared immutable identity."""


@dataclass(frozen=True)
class ArtifactRef:
    """A portable logical path and its verified SHA-256 digest."""

    path: str
    sha256: str
    byte_count: int


def _validate_checksum(checksum: str) -> None:
    if not _SHA256_RE.fullmatch(checksum):
        raise ArtifactIntegrityError(
            "SHA-256 digests must be 64 lowercase hex characters"
        )


def _normalise_namespace(namespace: str) -> str:
    path = PurePosixPath(namespace)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ArtifactIntegrityError(
            "artifact namespace must be a relative logical path"
        )
    if not all(_NAMESPACE_PART_RE.fullmatch(part) for part in path.parts):
        raise ArtifactIntegrityError(
            "artifact namespace contains an unsafe path component"
        )
    return path.as_posix()


class ContentAddressedArtifactStore:
    """Write-once local artifact store with checksum-encoded logical paths.

    Files are addressed as ``<namespace>/sha256/<digest>``.  The logical path is
    stored in the database instead of a machine-specific absolute path, so a
    restored artifact directory can reproduce a run on a fresh process.
    """

    def __init__(self, root: Path):
        self.root = root

    def put_bytes(
        self,
        namespace: str,
        content: bytes,
        *,
        declared_sha256: str | None = None,
    ) -> ArtifactRef:
        """Atomically store bytes, refusing an incorrect caller-supplied hash."""
        digest = sha256(content).hexdigest()
        if declared_sha256 is not None:
            _validate_checksum(declared_sha256)
            if declared_sha256 != digest:
                raise ArtifactIntegrityError(
                    "declared SHA-256 does not match artifact bytes"
                )
        namespace = _normalise_namespace(namespace)
        logical_path = f"{namespace}/sha256/{digest}"
        target = self.root / logical_path
        target.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_path = mkstemp(
            prefix=".artifact-", dir=target.parent
        )
        try:
            with os.fdopen(file_descriptor, "wb") as artifact:
                artifact.write(content)
                artifact.flush()
                os.fsync(artifact.fileno())
            try:
                # link(2) refuses to replace an existing target. That gives
                # concurrent writers a read-only, fully-written winner.
                os.link(temporary_path, target)
            except FileExistsError:
                self.verify(logical_path, digest)
        finally:
            Path(temporary_path).unlink(missing_ok=True)
        return ArtifactRef(logical_path, digest, len(content))

    def verify(self, logical_path: str, expected_sha256: str) -> ArtifactRef:
        """Verify a referenced artifact and its content-addressed path."""
        _validate_checksum(expected_sha256)
        candidate = PurePosixPath(logical_path)
        expected_suffix = ("sha256", expected_sha256)
        if (
            candidate.is_absolute()
            or ".." in candidate.parts
            or candidate.parts[-2:] != expected_suffix
        ):
            raise ArtifactIntegrityError(
                "artifact checksum failure: path does not name the declared "
                "content-addressed SHA-256"
            )
        file_path = self.root / candidate.as_posix()
        if not file_path.is_file():
            raise ArtifactIntegrityError(f"artifact is missing: {logical_path}")
        actual = sha256(file_path.read_bytes()).hexdigest()
        if actual != expected_sha256:
            raise ArtifactIntegrityError(
                f"artifact checksum failure for {logical_path}: expected "
                f"{expected_sha256}, got {actual}"
            )
        return ArtifactRef(logical_path, actual, file_path.stat().st_size)

    def model_path(self, model_id: str, checksum: str) -> str:
        """Return the only permitted logical path for a named model artifact."""
        _validate_checksum(checksum)
        model_id = _normalise_namespace(model_id)
        return f"models/{model_id}/sha256/{checksum}"
