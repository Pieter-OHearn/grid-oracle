"""Add the recoverable WP04 scheduler ledger.

Revision ID: 20260929_05
Revises: 20260929_04
"""

import sqlalchemy as sa
from alembic import op

revision = "20260929_05"
down_revision = "20260929_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing snapshots stay readable; availability and provider-validity are
    # additive so an unavailable forecast cannot be mistaken for dry weather.
    op.add_column(
        "weather_snapshots",
        sa.Column("availability", sa.String(24), nullable=True),
    )
    op.add_column(
        "weather_snapshots",
        sa.Column("issue_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "weather_snapshots",
        sa.Column("release_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "orchestration_jobs",
        sa.Column("job_key", sa.String(220), primary_key=True),
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("races.id"), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_owner", sa.String(100)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_orchestration_jobs_due", "orchestration_jobs", ["status", "due_at"]
    )
    op.create_table(
        "orchestration_job_dependencies",
        sa.Column(
            "job_key",
            sa.String(220),
            sa.ForeignKey("orchestration_jobs.job_key"),
            primary_key=True,
        ),
        sa.Column(
            "dependency_key",
            sa.String(220),
            sa.ForeignKey("orchestration_jobs.job_key"),
            primary_key=True,
        ),
    )
    op.create_table(
        "orchestration_calendar_revisions",
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("races.id"), primary_key=True),
        sa.Column("fingerprint", sa.String(64), primary_key=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("orchestration_calendar_revisions")
    op.drop_table("orchestration_job_dependencies")
    op.drop_index("ix_orchestration_jobs_due", table_name="orchestration_jobs")
    op.drop_table("orchestration_jobs")
    op.drop_column("weather_snapshots", "release_at")
    op.drop_column("weather_snapshots", "issue_at")
    op.drop_column("weather_snapshots", "availability")
