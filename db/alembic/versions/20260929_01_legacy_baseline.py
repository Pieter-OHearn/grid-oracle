"""Recognized legacy SQL-migration baseline.

Revision ID: 20260929_01
Revises:
Create Date: 2026-09-29
"""

revision = "20260929_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op: only stamped after legacy schema inspection by db_migrate."""


def downgrade() -> None:
    """No-op: legacy SQL tables predate the Alembic ledger and are preserved."""
