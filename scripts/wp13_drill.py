"""Disposable native-image install/upgrade/restart/restore acceptance drill.

Only randomly named local Compose projects are created. No homelab hostname,
provider, training machine, production data, or public listener is contacted.
"""

import argparse
import json
import platform
import re
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from contextlib import suppress
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "deploy/wp13/staging.compose.yml"
PIN = re.compile(
    r"^ghcr\.io/[a-z0-9-]+/gridoracle-(api|worker|frontend):v\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?@sha256:[0-9a-f]{64}$"
)


def run(*args, input=None):
    result = subprocess.run(args, input=input, capture_output=True, check=False)
    if result.returncode:
        # Commands contain only disposable file paths/config, never credentials.
        raise RuntimeError(result.stderr.decode()[-4000:])
    return result.stdout


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def get(url):
    with build_opener(ProxyHandler({})).open(url, timeout=10) as response:
        return response.status, response.read(), response.headers.get_content_type()


def wait_ready(url):
    last_error = None
    for _ in range(30):
        try:
            if get(url)[0] == 200:
                return
        except (OSError, HTTPError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise ValueError(f"staging runtime did not become ready: {last_error}")


BUNDLE_SEED = """
import json, os
from pathlib import Path
from gridoracle.provenance import ContentAddressedArtifactStore
s=ContentAddressedArtifactStore(Path('/artifacts'))
refs={}
for key,ns,data in [
 ('model','models/fixture',b'model'),
 ('training_data','datasets/fixture',b'data'),
 ('feature_schema','schemas/fixture',b'schema'),
 ('calibration','calibrators/fixture',b'calibrator')
]:
 r=s.put_bytes(ns,data); refs[key]={'id':'fixture','path':r.path,'sha256':r.sha256}
b={'format':'gridoracle-model-bundle-v1',**refs,'artifacts':list(refs.values()),'model_manifest_id':'model','dataset_id':'dataset','feature_snapshot_id':'features','calibrator_manifest_id':'calibrator','code_revision':'synthetic-staging-fixture','runtime_image':os.environ['FIXTURE_IMAGE']}
Path('/fixture/bundle.json').write_text(json.dumps(b,sort_keys=True))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--candidate", action="store_true")
    mode.add_argument("--release-json", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.candidate:
        images = {
            role: f"gridoracle-{role}:candidate"
            for role in ("api", "worker", "frontend")
        }
    else:
        release = json.loads(args.release_json.read_text())
        images = {
            role: release["images"][role]["pin"]
            for role in ("api", "worker", "frontend")
        }
        for role, image in images.items():
            if not PIN.fullmatch(image) or PIN.fullmatch(image)[1] != role:
                raise ValueError("staging requires a version-and-digest-pinned release")
    report = {
        "passed": False,
        "mode": "candidate" if args.candidate else "released-digest",
        "architecture": platform.machine(),
        "images": images,
        "checks": [],
        "fixture": "synthetic WP11 saved forecasts; no model-quality or training claim",
    }
    temporary = Path(tempfile.mkdtemp(prefix="gridoracle-wp13-drill-"))
    temporary.chmod(0o755)
    projects = ["wp13-" + uuid.uuid4().hex[:10] for _ in range(2)]
    configs = []
    try:
        for index in range(2):
            directory = temporary / str(index)
            directory.mkdir(mode=0o777)
            directory.chmod(0o777)
            for child in ("artifacts", "recovery"):
                (directory / child).mkdir(mode=0o777)
                (directory / child).chmod(0o777)
            (directory / "bundle.json").write_text("{}")
            (directory / "bundle.json").chmod(0o666)
            (directory / "url").write_text(
                "postgresql://gridoracle_admin@db:5432/gridoracle"
            )
            values = {
                "API_IMAGE": images["api"],
                "WORKER_IMAGE": images["worker"],
                "FRONTEND_IMAGE": images["frontend"],
                "ARTIFACTS": str(directory / "artifacts"),
                "BUNDLE": str(directory / "bundle.json"),
                "RECOVERY": str(directory / "recovery"),
                "DATABASE_URL_FILE": str(directory / "url"),
                "BUNDLE_SHA256": "0" * 64,
                "SEASON": "2022",
                "API_PORT": str(free_port()),
                "FRONTEND_PORT": str(free_port()),
            }
            env = directory / "compose.env"
            configs.append((directory, values, env))

        def compose(index, *command, input=None, fixture=False):
            directory, values, env = configs[index]
            env.write_text(
                "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
            )
            files = ["--file", str(STACK)]
            if fixture:
                override = directory / "fixture.override.yml"
                override.write_text(
                    "services:\n  tools:\n    volumes:\n"
                    "      - type: bind\n"
                    f"        source: {directory / 'artifacts'}\n"
                    "        target: /artifacts\n        read_only: false\n"
                )
                files += ["--file", str(override)]
            return run(
                "docker",
                "compose",
                "--project-name",
                projects[index],
                "--env-file",
                str(env),
                *files,
                *command,
                input=input,
            )

        def tool(index, *command, writable=False):
            directory = configs[index][0]
            mounts = ["-v", f"{directory}:/fixture"]
            return compose(
                index,
                "run",
                "--rm",
                "--no-deps",
                *mounts,
                "-e",
                f"FIXTURE_IMAGE={images['worker']}",
                "tools",
                *command,
                fixture=writable,
            )

        def dump(index, database):
            data = compose(
                index,
                "exec",
                "-T",
                "db",
                "pg_dump",
                "-U",
                "gridoracle_admin",
                "-Fc",
                "--no-owner",
                "--no-acl",
                database,
            )
            (configs[index][0] / "recovery/database.dump").write_bytes(data)
            return data

        def seal(index):
            return (
                tool(
                    index,
                    "-m",
                    "scripts.wp13_recovery",
                    "seal",
                    "--directory",
                    "/recovery",
                )
                .decode()
                .strip()
                .splitlines()[-1]
            )

        compose(0, "up", "-d", "--wait", "db")
        tool(0, "-c", BUNDLE_SEED, writable=True)
        directory, values, _ = configs[0]
        values["BUNDLE_SHA256"] = sha256(
            (directory / "bundle.json").read_bytes()
        ).hexdigest()
        dump(0, "gridoracle")
        initial_receipt = seal(0)
        tool(
            0,
            "-m",
            "scripts.wp13_migrate",
            "--backup",
            "/recovery",
            "--receipt-sha256",
            initial_receipt,
            "--bootstrap-empty",
        )
        revision = (
            compose(
                0,
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "gridoracle_admin",
                "-d",
                "gridoracle",
                "-Atc",
                "SELECT version_num FROM alembic_version",
            )
            .decode()
            .strip()
        )
        report["schema_upgrade"] = {
            "from": "empty -> inspected historical baseline",
            "to": revision,
            "backup_receipt_sha256": initial_receipt,
        }
        report["checks"].append(
            "backup-before-migration + explicit empty initialization + Alembic upgrade"
        )
        try:
            tool(
                0,
                "-m",
                "scripts.wp13_migrate",
                "--backup",
                "/recovery",
                "--receipt-sha256",
                initial_receipt,
            )
        except RuntimeError as error:
            assert "schema changed since backup" in str(error)
        else:
            raise ValueError("stale pre-upgrade backup was incorrectly accepted")
        report["checks"].append("migration refuses a stale schema backup")
        (directory / "recovery").rename(directory / "initial-backup")
        (directory / "recovery").mkdir(mode=0o777)
        (directory / "recovery").chmod(0o777)
        dump(0, "gridoracle")
        current_receipt = seal(0)
        tool(
            0,
            "-m",
            "scripts.wp13_migrate",
            "--backup",
            "/recovery",
            "--receipt-sha256",
            current_receipt,
        )
        report["checks"].append(
            "repeat schema upgrade with a fresh backup is idempotent"
        )

        # A separate synthetic source database supplies saved, published WP03
        # forecasts. The freshly installed production-schema DB is retained.
        compose(
            0,
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "gridoracle_admin",
            "-d",
            "gridoracle",
            "-c",
            "CREATE DATABASE fixture",
        )
        url_file = directory / "url"
        url_file.write_text(url_file.read_text().rsplit("/", 1)[0] + "/fixture")
        tool(
            0,
            "-c",
            "from gridoracle.ops.runtime import configure; configure(); "
            "import os; from pathlib import Path; "
            "from api.tests.public_fixture import build_fixture; "
            "e,_,_=build_fixture(os.environ['DATABASE_URL'],Path('/artifacts')); "
            "e.dispose()",
            writable=True,
        )
        benchmark = compose(
            0,
            "run",
            "--rm",
            "--no-deps",
            "--entrypoint",
            "python",
            "worker",
            "-m",
            "scripts.wp13_benchmark",
        )
        report["backfill"] = json.loads(benchmark.decode().strip().splitlines()[-1])
        report["checks"].append(
            "native worker image and bounded single-event ledger backfill"
        )
        # Rotate to a new backup directory; sealed sets are never replaced.
        archive = directory / "upgrade-backup"
        (directory / "recovery").rename(archive)
        (directory / "recovery").mkdir(mode=0o777)
        (directory / "recovery").chmod(0o777)
        dump(0, "fixture")
        receipt = seal(0)
        report["recovery_receipt_sha256"] = receipt
        report["bundle_sha256"] = values["BUNDLE_SHA256"]
        report["lineage"] = json.loads(
            (directory / "recovery/recovery.json").read_text()
        )["lineage"]
        compose(0, "up", "-d", "--wait", "api", "frontend")
        front = f"http://127.0.0.1:{values['FRONTEND_PORT']}"
        compose(
            0, "exec", "-T", "api", "python", "-m", "gridoracle.ops.runtime", "ready"
        )
        wait_ready(front + "/health")
        route = "/api/v1/seasons/2022/events/2022/forecast?horizon=pre_weekend"
        saved = get(front + route)[1]
        assert len(json.loads(saved)["run"]["entries"]) == 22
        report["checks"].append(
            "non-root read-only API/frontend serve 22-entry published fixture"
        )
        for path in ("/metrics", "/ready", "/docs", "/openapi.json"):
            assert get(front + path)[2] == "text/html", path
        private_metrics = compose(
            0,
            "exec",
            "-T",
            "frontend",
            "wget",
            "-q",
            "-O",
            "-",
            "http://127.0.0.1:9090/metrics",
        )
        assert b"gridoracle_http_requests_total" in private_metrics
        report["checks"].append(
            "separate private metrics listener works; "
            "public listener cannot proxy operations/admin"
        )
        compose(0, "restart", "api", "frontend")
        compose(0, "up", "-d", "--wait", "api", "frontend")
        compose(
            0, "exec", "-T", "api", "python", "-m", "gridoracle.ops.runtime", "ready"
        )
        wait_ready(front + "/health")
        assert get(front + route)[1] == saved
        report["checks"].append(
            "restart serves identical saved forecast with training/providers absent"
        )
        timings = []
        for _ in range(100):
            start = time.monotonic()
            assert get(front + route)[1] == saved
            timings.append(time.monotonic() - start)
        report["latency_seconds"] = {
            "samples": 100,
            "concurrency": 1,
            "p50": sorted(timings)[49],
            "p95": sorted(timings)[94],
            "max": max(timings),
        }
        ids = compose(0, "ps", "-q").decode().split()
        report["memory"] = [
            json.loads(line)
            for line in run(
                "docker", "stats", "--no-stream", "--format", "{{json .}}", *ids
            )
            .decode()
            .splitlines()
        ]
        config = json.loads(compose(0, "config", "--format", "json"))
        assert not config["services"]["db"].get("ports")
        assert not config["services"]["api"].get("ports")
        assert all(
            p["host_ip"] == "127.0.0.1"
            for role in ("frontend",)
            for p in config["services"][role]["ports"]
        )
        report["checks"].append(
            "DB/API have no published port; frontend binds loopback only"
        )

        # Restore from copied archive/artifacts into a new Docker volume and
        # project, without any mount of the original application artifact tree.
        recovered, values2, _ = configs[1]
        # Content-addressed files are owned 0600 by UID10001 on Linux. Copy
        # with that same UID, never weaken production artifact permissions.
        shutil.rmtree(recovered / "recovery")  # empty, owned by the host runner
        run(
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
            "--user",
            "10001:10001",
            "--entrypoint",
            "python",
            "-v",
            f"{directory / 'recovery'}:/source:ro",
            "-v",
            f"{recovered}:/target",
            images["api"],
            "-c",
            "import shutil; shutil.copytree('/source','/target/recovery')",
        )
        values2["ARTIFACTS"] = str(recovered / "recovery/artifacts")
        values2["BUNDLE"] = str(recovered / "recovery/bundle.json")
        values2["BUNDLE_SHA256"] = values["BUNDLE_SHA256"]
        tool(
            1,
            "-m",
            "scripts.wp13_recovery",
            "verify",
            "--directory",
            "/recovery",
            "--receipt-sha256",
            receipt,
        )
        compose(1, "up", "-d", "--wait", "db")
        start = time.monotonic()
        compose(
            1,
            "exec",
            "-T",
            "db",
            "pg_restore",
            "-U",
            "gridoracle_admin",
            "-d",
            "gridoracle",
            "--no-owner",
            "--no-acl",
            "--exit-on-error",
            input=(recovered / "recovery/database.dump").read_bytes(),
        )
        tool(
            1,
            "-m",
            "scripts.wp13_recovery",
            "compare",
            "--directory",
            "/recovery",
            "--receipt-sha256",
            receipt,
        )
        compose(1, "up", "-d", "--wait", "api", "frontend")
        compose(
            1, "exec", "-T", "api", "python", "-m", "gridoracle.ops.runtime", "ready"
        )
        wait_ready(f"http://127.0.0.1:{values2['FRONTEND_PORT']}/health")
        assert get(f"http://127.0.0.1:{values2['FRONTEND_PORT']}" + route)[1] == saved
        report["restore_seconds"] = time.monotonic() - start
        report["checks"].append(
            "new environment restore verifies all lineage/output hashes, "
            "bundle and identical public response"
        )
        report["passed"] = True
    except Exception as exc:
        report["error"] = str(exc)
        for index in range(len(configs)):
            with suppress(Exception):
                report.setdefault("failure_logs", []).append(
                    compose(index, "logs", "--tail", "30").decode()[-6000:]
                )
        raise
    finally:
        for index, _project in enumerate(projects):
            if index < len(configs):
                try:
                    compose(index, "down", "--volumes", "--remove-orphans")
                except Exception as cleanup_error:
                    report.setdefault("cleanup_errors", []).append(str(cleanup_error))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        # Only synthetic, randomly named drill directories are relaxed for
        # their host owner's deletion; runtime source mounts remain read-only.
        try:
            run(
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
                "--user",
                "10001:10001",
                "--entrypoint",
                "python",
                "-v",
                f"{temporary}:/cleanup",
                images["api"],
                "-c",
                "import os; from pathlib import Path; "
                "[p.chmod(0o777) for p in Path('/cleanup').rglob('*') "
                "if p.is_dir() and p.stat().st_uid == os.getuid()]",
            )
            shutil.rmtree(temporary)
        except Exception as cleanup_error:
            report.setdefault("cleanup_errors", []).append(str(cleanup_error))
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            raise
    print(f"Passed {len(report['checks'])} staging/recovery checks")


if __name__ == "__main__":
    main()
