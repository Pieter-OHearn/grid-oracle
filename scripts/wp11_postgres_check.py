"""Public-contract check against an explicitly empty disposable PostgreSQL DB."""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.database import get_db
from api.main import create_app
from api.tests.public_fixture import build_fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if not args.database_url.startswith("postgresql://"):
        parser.error("Requires an explicitly empty disposable PostgreSQL database")
    engine, _, ids = build_fixture(args.database_url, args.artifacts)
    application = create_app(legacy=False)

    def database():
        with Session(engine) as db:
            yield db

    application.dependency_overrides[get_db] = database
    base = "/api/v1/seasons/2022/events/2022"
    checks = []
    try:
        with TestClient(application) as client:
            seasons = client.get("/api/v1/seasons")
            assert seasons.status_code == 200
            assert seasons.json()["seasons"][0]["coverage"]["available"] is None
            checks.append("Native ruleset/coverage projection")
            event = client.get(base).json()
            assert event["circuit_name"] == "Fixture circuit 2022"
            checks.append("Date-valid historical alias binding")
            run = client.get(base + "/forecast?horizon=pre_weekend").json()["run"]
            assert len(run["entries"]) == 22
            assert abs(sum(e["win_probability"] for e in run["entries"]) - 1) < 1e-10
            assert "private" not in str(run) and "internal_secret" not in str(run)
            checks.append("Native JSON allowlist and 22-entry probabilities")
            assert run["freshness"]["input_cutoff_at"] == "2022-04-30T23:00:00Z"
            checks.append("Native timezone-aware timestamp serialization")
            assert (
                client.get(base + "/forecast?horizon=post_qualifying").json()["state"]
                == "unavailable"
            )
            assert (
                client.get(base + "/runs/" + ids[(2022, "post_qualifying")]).status_code
                == 404
            )
            checks.append("Unpublished horizon and run remain private")
            sessions = client.get(base + "/sessions").json()["sessions"]
            assert len(sessions) == 2
            assert next(s for s in sessions if s["kind"] == "race")["revision"] == 2
            checks.append("Latest session revisions")
            assert client.get("/api/v1/seasons/2026/events/2022").status_code == 404
            checks.append("Cross-season resource isolation")
        args.report.write_text(
            json.dumps(
                {
                    "database": "Disposable PostgreSQL 16; synthetic fixture only",
                    "passed": True,
                    "checks": checks,
                },
                indent=2,
            )
            + "\n"
        )
    finally:
        engine.dispose()
    print(f"Passed {len(checks)} PostgreSQL public-contract checks")


if __name__ == "__main__":
    main()
