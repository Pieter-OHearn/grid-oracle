"""Coordinated nightly recovery sets, for a sidecar beside the database.

`backup` takes the maintenance lock exclusively, so running scheduler and
worker ticks finish and no new tick starts; dumps the database with the
PostgreSQL 16 client; seals the set with the artifact tree and the selected
bundle; releases the lock; verifies the set from disk; and only then moves it
into `sets/`, with its receipt hash beside it in `receipts/`. Older sets are
pruned to a small local count: the backup server keeps the history.

Every folder in a set is 0755 and every file 0644, so the platform's backup
user can read it. Layout under the root (one mount, so the final move is an
atomic rename):

    sets/<UTC timestamp>/          sealed recovery sets
    receipts/<UTC timestamp>.sha256
    status/status.json             read by the API's /metrics
    .staging-<UTC timestamp>/      in progress; removed on failure
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from gridoracle.ops.recovery import verify_recovery_set
from gridoracle.ops.runtime import MAINTENANCE_LOCK, configure

MAX_AGE = timedelta(hours=26)
# After a failed attempt, wait this long before the next one.
RETRY = timedelta(minutes=30)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def _status(root: Path) -> dict:
    path = root / "status" / "status.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _dump(url: str, target: Path) -> None:
    parsed = make_url(url)
    environment = {
        **os.environ,
        "PGHOST": parsed.host or "",
        "PGPORT": str(parsed.port or 5432),
        "PGUSER": parsed.username or "",
        "PGDATABASE": parsed.database or "",
        # The password goes in the environment, never on the command line.
        "PGPASSWORD": parsed.password or "",
    }
    subprocess.run(
        [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-acl",
            f"--file={target}",
        ],
        env=environment,
        check=True,
        timeout=1800,
    )


def publishable(directory: Path) -> None:
    """Make a set readable by the platform's backup user: folders 0755, files 0644.

    The artifact store writes each file through `mkstemp` (0600), and sealing
    copies modes, so without this the off-host copy can't read the artifacts.
    """
    directory.chmod(0o755)
    for path in directory.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)


def verify_all(root: Path) -> tuple[int, int]:
    """Verify every retained set against its receipt: (verified, failed)."""
    verified = failed = 0
    for directory in sorted((root / "sets").glob("*")):
        receipt = root / "receipts" / f"{directory.name}.sha256"
        try:
            verify_recovery_set(directory, receipt.read_text().strip())
        except Exception:
            failed += 1
        else:
            verified += 1
    return verified, failed


def prune(root: Path, keep: int) -> None:
    sets = sorted((root / "sets").glob("*"))
    for directory in sets[: max(0, len(sets) - keep)]:
        shutil.rmtree(directory)
        (root / "receipts" / f"{directory.name}.sha256").unlink(missing_ok=True)


def backup(root: Path, *, keep: int, now: datetime | None = None) -> dict:
    from scripts.wp13_recovery import seal

    configure()
    url = os.environ["DATABASE_URL"]
    now = now or datetime.now(UTC)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    name, suffix = stamp, 1
    while (root / "sets" / name).exists() or (
        root / "receipts" / f"{name}.sha256"
    ).exists():
        # A set name is never reused, so a receipt can't describe another set.
        name, suffix = f"{stamp}-{suffix}", suffix + 1
    staging = root / f".staging-{name}"
    for leftover in root.glob(".staging-*"):
        shutil.rmtree(leftover)
    staging.mkdir(parents=True)
    (root / "sets").mkdir(exist_ok=True)
    (root / "receipts").mkdir(exist_ok=True)
    engine = create_engine(url)
    try:
        with engine.connect() as gate:
            gate.execute(
                text("SELECT pg_advisory_lock(:key)"), {"key": MAINTENANCE_LOCK}
            )
            try:
                _dump(url, staging / "database.dump")
                receipt = seal(
                    staging,
                    Path(os.environ["GRIDORACLE_ARTIFACT_ROOT"]),
                    Path(os.environ["GRIDORACLE_BUNDLE_FILE"]),
                    os.environ["GRIDORACLE_BUNDLE_SHA256"],
                )
            finally:
                gate.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": MAINTENANCE_LOCK}
                )
        publishable(staging)
        verify_recovery_set(staging, receipt)
        os.replace(staging, root / "sets" / name)
        # Written last: a set without its receipt fails verification visibly.
        (root / "receipts" / f"{name}.sha256").write_text(receipt + "\n")
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        engine.dispose()
    prune(root, keep)
    size = sum(
        p.stat().st_size for p in (root / "sets" / name).rglob("*") if p.is_file()
    )
    return {"set": name, "receipt_sha256": receipt, "bytes": size}


def run(root: Path, *, keep: int) -> bool:
    """One attempt with its status recorded; the status never holds secrets."""
    status = _status(root)
    attempted = datetime.now(UTC)
    try:
        result = backup(root, keep=keep, now=attempted)
    except Exception as error:
        status.update(
            last_attempt_at=attempted.isoformat(),
            last_attempt_ok=False,
            last_error=type(error).__name__,
        )
        ok = False
    else:
        status.update(
            last_attempt_at=attempted.isoformat(),
            last_attempt_ok=True,
            last_error=None,
            last_success_at=attempted.isoformat(),
            last_set=result["set"],
            last_receipt_sha256=result["receipt_sha256"],
            last_bytes=result["bytes"],
        )
        ok = True
    verified, failed = verify_all(root)
    status.update(verified_sets=verified, failed_sets=failed)
    _write_json(root / "status" / "status.json", status)
    print(
        json.dumps(
            {
                "service": "gridoracle-backup",
                "level": "info" if ok and not failed else "error",
                "event": "backup",
                "ok": ok,
                "set": status.get("last_set"),
                "verified_sets": verified,
                "failed_sets": failed,
            }
        ),
        flush=True,
    )
    return ok and not failed


def healthy(root: Path, now: datetime | None = None) -> bool:
    status = _status(root)
    success = status.get("last_success_at")
    if not success or status.get("failed_sets", 1):
        return False
    return (now or datetime.now(UTC)) - datetime.fromisoformat(success) <= MAX_AGE


def _sealed_day(root: Path, hour: int) -> date | None:
    """The day whose nightly set is already sealed, from the newest set's name.

    A set counts for its UTC day when it was sealed at or after `hour`; one
    sealed earlier is the night before's, so that day's nightly is still due.
    """
    for directory in sorted((root / "sets").glob("*"), reverse=True):
        try:
            sealed = datetime.strptime(directory.name[:16], "%Y%m%dT%H%M%SZ")
        except ValueError:
            continue
        return sealed.date() if sealed.hour >= hour else None
    return None


def loop(root: Path, *, keep: int, hour: int) -> None:
    """Run nightly at `hour` UTC, and at once when no fresh set exists.

    The nightly day starts from the sets on disk, so a restart later that day
    (every deploy) doesn't seal another set and prune one not yet copied.
    """
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    last_day, last_try = _sealed_day(root, hour), None
    while not stopping:
        now = datetime.now(UTC)
        nightly = now.hour >= hour and last_day != now.date()
        stale = not healthy(root, now) and (last_try is None or now - last_try >= RETRY)
        if nightly or stale:
            last_try = now
            if run(root, keep=keep):
                last_day = now.date()
        for _ in range(60):
            if stopping:
                break
            time.sleep(1)


def backup_metrics(path: str | None) -> list[str]:
    """Prometheus rows for the status file, when this deployment mounts it."""
    if not path:
        return []
    rows = ["# TYPE gridoracle_backup_status_present gauge"]
    try:
        status = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return [*rows, "gridoracle_backup_status_present 0"]
    success = status.get("last_success_at")
    gauges = {
        "gridoracle_backup_status_present": 1,
        "gridoracle_backup_last_success_timestamp_seconds": (
            datetime.fromisoformat(success).timestamp() if success else 0
        ),
        "gridoracle_backup_last_attempt_success": int(
            bool(status.get("last_attempt_ok"))
        ),
        "gridoracle_backup_verified_sets": int(status.get("verified_sets") or 0),
        "gridoracle_backup_failed_sets": int(status.get("failed_sets") or 0),
        "gridoracle_backup_last_bytes": int(status.get("last_bytes") or 0),
    }
    for name, value in gauges.items():
        if name != "gridoracle_backup_status_present":
            rows.append(f"# TYPE {name} gauge")
        rows.append(f"{name} {value}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("backup", "loop", "check"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--keep", type=int, default=2)
    parser.add_argument("--hour", type=int, default=2)
    args = parser.parse_args()
    if args.action == "check":
        sys.exit(0 if healthy(args.root) else 1)
    if args.action == "backup":
        sys.exit(0 if run(args.root, keep=args.keep) else 1)
    loop(args.root, keep=args.keep, hour=args.hour)


if __name__ == "__main__":
    main()
