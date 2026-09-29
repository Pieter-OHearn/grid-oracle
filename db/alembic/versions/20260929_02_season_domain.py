"""Add season-aware domain contracts without rewriting legacy facts.

Revision ID: 20260929_02
Revises: 20260929_01
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20260929_02"
down_revision = "20260929_01"
branch_labels = None
depends_on = None


def _identity_column() -> sa.Column[sa.String]:
    return sa.Column("identity_key", sa.String(length=160), nullable=True)


def upgrade() -> None:
    for table, prefix in (("drivers", "driver"), ("constructors", "team"), ("circuits", "circuit")):
        op.add_column(table, _identity_column())
        op.execute(f"UPDATE {table} SET identity_key = 'legacy:{prefix}:' || id WHERE identity_key IS NULL")
        op.create_index(f"ux_{table}_identity_key", table, ["identity_key"], unique=True)

    op.add_column("races", sa.Column("event_key", sa.String(length=160), nullable=True))
    op.add_column("races", sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="scheduled"))
    op.add_column("races", sa.Column("schedule_revision", sa.Integer(), nullable=False, server_default="1"))
    op.execute("UPDATE races SET event_key = 'legacy:event:' || id WHERE event_key IS NULL")
    op.create_index("ux_races_event_key", "races", ["event_key"], unique=True)

    op.create_table(
        "season_rulesets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("ruleset_version", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("season", "ruleset_version", name="uq_season_rulesets_version"),
    )
    op.create_table(
        "entity_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_kind", sa.String(length=32), nullable=False),
        sa.Column("identity_key", sa.String(length=160), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("provider_key", sa.String(length=200), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_display_alias", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("entity_kind", "provider", "provider_key", name="uq_entity_alias_provider"),
    )
    op.create_table(
        "circuit_layouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("identity_key", sa.String(length=160), nullable=False, unique=True),
        sa.Column("circuit_id", sa.Integer(), sa.ForeignKey("circuits.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("configuration_hash", sa.String(length=128), nullable=True),
    )
    op.create_table(
        "event_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("races.id"), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="scheduled"),
        sa.UniqueConstraint("race_id", "kind", "revision", name="uq_event_sessions_revision"),
    )
    op.create_table(
        "event_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("races.id"), nullable=False),
        sa.Column("driver_id", sa.Integer(), sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("constructor_id", sa.Integer(), sa.ForeignKey("constructors.id"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("replaces_entry_id", sa.Integer(), sa.ForeignKey("event_entries.id"), nullable=True),
        sa.UniqueConstraint("race_id", "driver_id", "revision", name="uq_event_entries_driver_revision"),
    )
    op.create_table(
        "result_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("races.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=False),
        sa.Column("is_official", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("race_id", "revision", name="uq_result_revisions_race_revision"),
    )
    op.create_table(
        "identity_quarantine",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_kind", sa.String(length=32), nullable=False),
        sa.Column("legacy_identifier", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("entity_kind", "legacy_identifier", "reason", name="uq_identity_quarantine_issue"),
    )


def downgrade() -> None:
    for table in (
        "identity_quarantine",
        "result_revisions",
        "event_entries",
        "event_sessions",
        "circuit_layouts",
        "entity_aliases",
        "season_rulesets",
    ):
        op.drop_table(table)
    op.drop_index("ux_races_event_key", table_name="races")
    op.drop_column("races", "schedule_revision")
    op.drop_column("races", "lifecycle_status")
    op.drop_column("races", "event_key")
    for table in ("circuits", "constructors", "drivers"):
        op.drop_index(f"ux_{table}_identity_key", table_name=table)
        op.drop_column(table, "identity_key")
