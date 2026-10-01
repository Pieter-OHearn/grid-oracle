"""Disposable synthetic forecast/evaluation history for WP12 browser and API QA."""

import argparse
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from api.tests.public_fixture import build_fixture


def build_trust_fixture(url, artifacts):
    engine, store, ids = build_fixture(
        url,
        artifacts,
        horizon_probabilities={
            "pre_weekend": [0.20, 0, None] + [0.8 / 19] * 19,
            "post_qualifying": [0.25, 0, None] + [0.75 / 19] * 19,
        },
    )
    for year in (2022, 2026):
        store.publish(
            ids[(year, "post_qualifying")],
            published_at=datetime(year, 5, 3, 18, tzinfo=UTC),
        )
        with engine.begin() as conn:
            for revision in (1, 2, 3):
                conn.execute(
                    text(
                        "INSERT INTO result_revisions "
                        "(id,race_id,revision,source,reason,is_official,recorded_at) "
                        "VALUES (:id,:year,:revision,'/private/source',"
                        "'internal_secret correction',true,:time)"
                    ),
                    {
                        "id": year * 10 + revision,
                        "year": year,
                        "revision": revision,
                        "time": f"{year}-05-0{4 + revision}T18:00:00+00:00",
                    },
                )
        for revision, loss in ((1, 1.6094379124341003), (2, 3.1675825304806504)):
            store.record_evaluation(
                evaluation_id=f"private-evaluation-{year}-{revision}",
                forecast_run_id=ids[(year, "pre_weekend")],
                result_revision_id=year * 10 + revision,
                evaluator_manifest={
                    "public_contract": "wp12-v1",
                    "private": "/private/secret",
                },
                metrics={
                    "values": {
                        "winner_log_loss": loss,
                        "winner_hit": 1 if revision == 1 else 0,
                        "top3_overlap": 2 / 3,
                        "top10_overlap": None,
                        "internal_secret": "never public",
                    },
                    "observations": {
                        "winner_log_loss": 1,
                        "winner_hit": 1,
                        "top3_overlap": 1,
                        "top10_overlap": 0,
                    },
                },
                evaluated_at=datetime(year, 5, 5 + revision, 19, tzinfo=UTC),
            )
    return engine, store, ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    engine, _, _ = build_trust_fixture(
        f"sqlite:///{args.database}", args.database.parent / "wp12-artifacts"
    )
    engine.dispose()
