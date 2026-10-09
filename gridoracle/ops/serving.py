"""Production wrapper; private readiness and low-cardinality operational metrics."""

import json
import os
import time
from collections import Counter
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text

from api.database import engine
from api.main import create_app
from gridoracle.ops.backup import backup_metrics
from gridoracle.ops.bundle import file_digest, verify_selection
from gridoracle.ops.runtime import bundle_check

schema_config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
schema_config.set_main_option(
    "script_location", str(Path(__file__).resolve().parents[2] / "db/alembic")
)
schema_head = ScriptDirectory.from_config(schema_config).get_current_head()
verified_bundle = bundle_check()
app = create_app(legacy=False)
counts = Counter()
latency = Counter()
BUCKETS = (0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0)


@app.middleware("http")
async def operational_request(request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    elapsed = time.monotonic() - start
    # Route templates have bounded cardinality; unmatched/invalid paths never
    # become labels. Query strings, IDs and exception messages are excluded.
    route = getattr(request.scope.get("route"), "path", "unmatched")
    if route not in ("/metrics", "/health", "/ready"):
        status = f"{response.status_code // 100}xx"
        counts[route, status] += 1
        latency[route, "sum"] += elapsed
        latency[route, "count"] += 1
        for bucket in BUCKETS:
            latency[route, str(bucket)] += elapsed <= bucket
        print(
            json.dumps(
                {
                    "service": "gridoracle-api",
                    "level": "error" if response.status_code >= 500 else "info",
                    "route": route,
                    "status": response.status_code,
                    "duration_seconds": elapsed,
                }
            ),
            flush=True,
        )
    return response


@app.get("/ready", include_in_schema=False)
def ready():
    try:
        if (
            file_digest(Path(os.environ["GRIDORACLE_BUNDLE_FILE"]))
            != os.environ["GRIDORACLE_BUNDLE_SHA256"]
        ):
            raise ValueError("selected bundle manifest changed")
        verify_selection(engine, verified_bundle)
        with engine.connect() as conn:
            if (
                conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                != schema_head
            ):
                raise ValueError("database requires the released schema revision")
            conn.execute(
                text("SELECT COUNT(*) FROM forecast_publications")
            ).scalar_one()
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
def metrics():
    rows = [
        "# TYPE gridoracle_http_requests_total counter",
        "# TYPE gridoracle_http_duration_seconds histogram",
    ]
    for (route, status), count in sorted(counts.items()):
        rows.append(
            f'gridoracle_http_requests_total{{route="{route}",'
            f'status="{status}"}} {count}'
        )
    for route in sorted({key[0] for key in latency}):
        for bucket in BUCKETS:
            rows.append(
                f'gridoracle_http_duration_seconds_bucket{{route="{route}",'
                f'le="{bucket}"}} {latency[route, str(bucket)]}'
            )
        rows.append(
            f'gridoracle_http_duration_seconds_bucket{{route="{route}",'
            f'le="+Inf"}} {latency[route, "count"]}'
        )
        for suffix in ("count", "sum"):
            rows.append(
                f'gridoracle_http_duration_seconds_{suffix}{{route="{route}"}} '
                f"{latency[route, suffix]}"
            )
    rows.extend(backup_metrics(os.getenv("GRIDORACLE_BACKUP_STATUS_FILE")))
    # Fixed-state labels only: no event, driver, job-key, model or run labels.
    with engine.connect() as conn:
        for state in ("pending", "running", "succeeded", "blocked", "superseded"):
            count = conn.execute(
                text("SELECT COUNT(*) FROM orchestration_jobs WHERE status=:state"),
                {"state": state},
            ).scalar_one()
            rows.append(f'gridoracle_jobs{{state="{state}"}} {count}')
    return PlainTextResponse(
        "\n".join(rows) + "\n", media_type="text/plain; version=0.0.4"
    )
