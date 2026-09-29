"""Add append-only provenance and publication lineage for WP03.

Revision ID: 20260929_04
Revises: 20260929_03
Create Date: 2026-09-29
"""

# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op

revision = "20260929_04"
down_revision = "20260929_03"
branch_labels = None
depends_on = None


_IMMUTABLE_TABLES = (
    "raw_provider_snapshots",
    "dataset_manifests",
    "feature_snapshots",
    "model_manifests",
    "calibrator_manifests",
    "forecast_runs",
    "forecast_entry_outputs",
    "evaluation_runs",
    "forecast_publications",
    "result_revisions",
)


def _immutable_triggers() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION gridoracle_prevent_history_mutation() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'immutable provenance records cannot be updated or deleted';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for table in _IMMUTABLE_TABLES:
            op.execute(
                f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION gridoracle_prevent_history_mutation()"
            )
    else:
        for table in _IMMUTABLE_TABLES:
            op.execute(
                f"""
                CREATE TRIGGER trg_{table}_immutable_update
                BEFORE UPDATE ON {table}
                BEGIN
                    SELECT RAISE(ABORT, 'immutable provenance records cannot be updated');
                END
                """
            )
            op.execute(
                f"""
                CREATE TRIGGER trg_{table}_immutable_delete
                BEFORE DELETE ON {table}
                BEGIN
                    SELECT RAISE(ABORT, 'immutable provenance records cannot be deleted');
                END
                """
            )


def _drop_immutable_triggers() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for table in _IMMUTABLE_TABLES:
            op.execute(f"DROP TRIGGER trg_{table}_immutable ON {table}")
        op.execute("DROP FUNCTION gridoracle_prevent_history_mutation()")
    else:
        for table in _IMMUTABLE_TABLES:
            op.execute(f"DROP TRIGGER trg_{table}_immutable_update")
            op.execute(f"DROP TRIGGER trg_{table}_immutable_delete")


def upgrade() -> None:
    op.create_table(
        "raw_provider_snapshots",
        sa.Column("snapshot_id", sa.String(length=96), primary_key=True),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("artifact_path", sa.String(length=700), nullable=False, unique=True),
        sa.Column("sha256", sa.String(length=64), nullable=False, unique=True),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("provenance_grade", sa.String(length=32), nullable=False),
    )
    op.create_table(
        "dataset_manifests",
        sa.Column("dataset_id", sa.String(length=96), primary_key=True),
        sa.Column("artifact_path", sa.String(length=700), nullable=False, unique=True),
        sa.Column("sha256", sa.String(length=64), nullable=False, unique=True),
        sa.Column("manifest", sa.JSON(), nullable=False),
    )
    op.create_table(
        "feature_snapshots",
        sa.Column("feature_snapshot_id", sa.String(length=96), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.String(length=96),
            sa.ForeignKey("dataset_manifests.dataset_id"),
            nullable=False,
        ),
        sa.Column("artifact_path", sa.String(length=700), nullable=False, unique=True),
        sa.Column("sha256", sa.String(length=64), nullable=False, unique=True),
        sa.Column("manifest", sa.JSON(), nullable=False),
    )
    op.create_table(
        "model_manifests",
        sa.Column("model_manifest_id", sa.String(length=96), primary_key=True),
        sa.Column("model_id", sa.String(length=160), nullable=False),
        sa.Column(
            "model_version_id",
            sa.Integer(),
            sa.ForeignKey("model_versions.id"),
            nullable=True,
        ),
        sa.Column("artifact_path", sa.String(length=700), nullable=False, unique=True),
        sa.Column("sha256", sa.String(length=64), nullable=False, unique=True),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "model_id", "sha256", name="uq_model_manifests_model_digest"
        ),
    )
    op.create_table(
        "calibrator_manifests",
        sa.Column("calibrator_manifest_id", sa.String(length=96), primary_key=True),
        sa.Column(
            "model_manifest_id",
            sa.String(length=96),
            sa.ForeignKey("model_manifests.model_manifest_id"),
            nullable=False,
        ),
        sa.Column("artifact_path", sa.String(length=700), nullable=False, unique=True),
        sa.Column("sha256", sa.String(length=64), nullable=False, unique=True),
        sa.Column("manifest", sa.JSON(), nullable=False),
    )
    op.create_table(
        "forecast_runs",
        sa.Column("forecast_run_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "idempotency_key", sa.String(length=200), nullable=False, unique=True
        ),
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("races.id"), nullable=False),
        sa.Column("horizon", sa.String(length=32), nullable=False),
        sa.Column("input_cutoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issue_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provenance_grade", sa.String(length=32), nullable=False),
        sa.Column("expected_entry_count", sa.Integer(), nullable=False),
        sa.Column("input_manifest", sa.JSON(), nullable=False),
        sa.Column(
            "raw_snapshot_id",
            sa.String(length=96),
            sa.ForeignKey("raw_provider_snapshots.snapshot_id"),
            nullable=True,
        ),
        sa.Column(
            "result_revision_id",
            sa.Integer(),
            sa.ForeignKey("result_revisions.id"),
            nullable=True,
        ),
        sa.Column(
            "dataset_id",
            sa.String(length=96),
            sa.ForeignKey("dataset_manifests.dataset_id"),
            nullable=True,
        ),
        sa.Column(
            "feature_snapshot_id",
            sa.String(length=96),
            sa.ForeignKey("feature_snapshots.feature_snapshot_id"),
            nullable=True,
        ),
        sa.Column(
            "model_manifest_id",
            sa.String(length=96),
            sa.ForeignKey("model_manifests.model_manifest_id"),
            nullable=True,
        ),
        sa.Column(
            "calibrator_manifest_id",
            sa.String(length=96),
            sa.ForeignKey("calibrator_manifests.calibrator_manifest_id"),
            nullable=True,
        ),
        sa.Column("reproduction_tolerance", sa.Float(), nullable=False),
        sa.Column("run_fingerprint", sa.String(length=64), nullable=False, unique=True),
        sa.CheckConstraint(
            "horizon IN ('pre_weekend', 'post_qualifying')",
            name="ck_forecast_runs_horizon",
        ),
        sa.CheckConstraint(
            "expected_entry_count > 0", name="ck_forecast_runs_entry_count"
        ),
        sa.CheckConstraint(
            "reproduction_tolerance >= 0", name="ck_forecast_runs_tolerance"
        ),
    )
    op.create_table(
        "forecast_entry_outputs",
        sa.Column(
            "forecast_run_id",
            sa.String(length=64),
            sa.ForeignKey("forecast_runs.forecast_run_id"),
            primary_key=True,
        ),
        sa.Column("entry_key", sa.String(length=200), primary_key=True),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("output_sha256", sa.String(length=64), nullable=False),
    )
    op.create_table(
        "evaluation_runs",
        sa.Column("evaluation_id", sa.String(length=96), primary_key=True),
        sa.Column(
            "forecast_run_id",
            sa.String(length=64),
            sa.ForeignKey("forecast_runs.forecast_run_id"),
            nullable=False,
        ),
        sa.Column(
            "result_revision_id",
            sa.Integer(),
            sa.ForeignKey("result_revisions.id"),
            nullable=False,
        ),
        sa.Column("evaluator_manifest", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "forecast_publications",
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("races.id"), primary_key=True),
        sa.Column("horizon", sa.String(length=32), primary_key=True),
        sa.Column(
            "forecast_run_id",
            sa.String(length=64),
            sa.ForeignKey("forecast_runs.forecast_run_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    )
    _immutable_triggers()


def downgrade() -> None:
    _drop_immutable_triggers()
    for table in (
        "forecast_publications",
        "evaluation_runs",
        "forecast_entry_outputs",
        "forecast_runs",
        "calibrator_manifests",
        "model_manifests",
        "feature_snapshots",
        "dataset_manifests",
        "raw_provider_snapshots",
    ):
        op.drop_table(table)
