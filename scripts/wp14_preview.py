"""Serve a built frontend and actual persisted replay API on loopback only."""

import argparse
import asyncio
import json
import os
import uuid
from pathlib import Path

import uvicorn
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from scripts.regression.replay import ROOT, WeekendReplay, initialize_legacy, time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, default=4174)
    args = parser.parse_args()
    url = os.environ["WP14_POSTGRES_URL"]
    args.output.mkdir(parents=True, exist_ok=True)
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    name = "wp14_" + uuid.uuid4().hex
    with admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {name}"))
    engine = create_engine(admin.url.set(database=name))
    os.environ["DATABASE_URL"] = str(engine.url)
    from api.database import get_db
    from api.main import create_app

    try:
        initialize_legacy(engine)
        replay = WeekendReplay(engine, args.output / "replay").complete()
        # Latest correction deliberately lacks a score; old evaluation survives.
        replay.now = time("2026-05-05T16:00:00+00:00")
        replay.result(correction=True)
        pending = WeekendReplay(
            engine, args.output / "replay", season=2027, race_id=2027
        )
        pending.drain()  # pre published; post remains unavailable in the real API
        app = create_app(legacy=False)

        @app.middleware("http")
        async def transport_fault(request, call_next):
            if request.url.path.startswith("/api/v1/"):
                if (args.output / "outage.flag").exists():
                    return JSONResponse(
                        {
                            "error": {
                                "code": "api_unavailable",
                                "message": "WP14 test transport outage",
                                "retryable": True,
                            }
                        },
                        status_code=503,
                    )
                if (args.output / "delay.flag").exists():
                    await asyncio.sleep(0.8)
            return await call_next(request)

        def database():
            with Session(engine) as db:
                yield db

        app.dependency_overrides[get_db] = database
        dist = ROOT / "dashboard/dist"
        assert (dist / "index.html").is_file(), "build dashboard first"

        @app.get("/{path:path}", include_in_schema=False)
        def frontend(path: str):
            target = (dist / path).resolve()
            if not target.is_relative_to(dist.resolve()):
                return FileResponse(dist / "index.html")
            return FileResponse(target if target.is_file() else dist / "index.html")

        (args.output / "replay.json").write_text(
            json.dumps(
                {
                    "passed": True,
                    "fixture_lineage": replay.manifest,
                    "runs": replay.runs,
                    "lineage": replay.hashes(),
                    "scope": "synthetic test adapter; real PostgreSQL + ledger + "
                    "baseline + public API; production adapter remains blocked",
                },
                indent=2,
            )
            + "\n"
        )
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE {name} WITH (FORCE)"))
        admin.dispose()


if __name__ == "__main__":
    main()
