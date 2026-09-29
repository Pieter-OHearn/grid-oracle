"""Ensure new identities and temporal aliases remain valid after WP02.

Revision ID: 20260929_03
Revises: 20260929_02
Create Date: 2026-09-29
"""

from alembic import op


revision = "20260929_03"
down_revision = "20260929_02"
branch_labels = None
depends_on = None


_IDENTITY_TABLES = (
    ("drivers", "identity_key", "driver"),
    ("constructors", "identity_key", "team"),
    ("circuits", "identity_key", "circuit"),
    ("races", "event_key", "event"),
)


def _postgres_identity_trigger(table: str, column: str, prefix: str) -> None:
    trigger = f"trg_{table}_{column}"
    function = (
        "gridoracle_assign_event_key"
        if column == "event_key"
        else "gridoracle_assign_identity_key"
    )
    op.execute(
        f"""
        CREATE TRIGGER {trigger}
        BEFORE INSERT OR UPDATE OF {column} ON {table}
        FOR EACH ROW EXECUTE FUNCTION {function}('{prefix}')
        """
    )


def _sqlite_identity_trigger(table: str, column: str, prefix: str) -> None:
    # SQLite cannot assign NEW.column in a BEFORE trigger. The nullable column
    # is therefore retained only for local migration fixtures; PostgreSQL, the
    # supported runtime, enforces NOT NULL in the same revision.
    op.execute(
        f"""
        CREATE TRIGGER trg_{table}_{column}
        AFTER INSERT ON {table}
        WHEN NEW.{column} IS NULL
        BEGIN
            UPDATE {table}
            SET {column} = '{prefix}:internal:' || NEW.id
            WHERE id = NEW.id;
        END
        """
    )


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION gridoracle_assign_identity_key() RETURNS trigger AS $$
            BEGIN
                IF NEW.identity_key IS NULL THEN
                    NEW.identity_key := TG_ARGV[0] || ':internal:' || NEW.id;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE FUNCTION gridoracle_assign_event_key() RETURNS trigger AS $$
            BEGIN
                IF NEW.event_key IS NULL THEN
                    NEW.event_key := TG_ARGV[0] || ':internal:' || NEW.id;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for table, column, prefix in _IDENTITY_TABLES:
            _postgres_identity_trigger(table, column, prefix)
            op.alter_column(table, column, nullable=False)
    else:
        for table, column, prefix in _IDENTITY_TABLES:
            _sqlite_identity_trigger(table, column, prefix)

    if dialect == "postgresql":
        op.drop_constraint(
            "uq_entity_alias_provider", "entity_aliases", type_="unique"
        )
        op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        op.execute(
            """
            ALTER TABLE entity_aliases
            ADD CONSTRAINT ex_entity_alias_provider_validity
            EXCLUDE USING gist (
                entity_kind WITH =,
                provider WITH =,
                provider_key WITH =,
                daterange(
                    COALESCE(valid_from, '-infinity'::date),
                    COALESCE(valid_to, 'infinity'::date),
                    '[)'
                ) WITH &&
            )
            """
        )
    else:
        with op.batch_alter_table("entity_aliases") as batch:
            batch.drop_constraint("uq_entity_alias_provider", type_="unique")
            batch.create_unique_constraint(
                "uq_entity_alias_provider_from",
                ["entity_kind", "provider", "provider_key", "valid_from"],
            )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        # Do not recreate the pre-WP02 global unique constraint: valid
        # time-bounded alias reuse may now exist and needs the documented
        # downgrade → backup restore path rather than a destructive rewrite.
        op.execute(
            "ALTER TABLE entity_aliases "
            "DROP CONSTRAINT ex_entity_alias_provider_validity"
        )
        for table, column, _prefix in _IDENTITY_TABLES:
            op.execute(f"DROP TRIGGER trg_{table}_{column} ON {table}")
            op.alter_column(table, column, nullable=True)
        op.execute("DROP FUNCTION gridoracle_assign_event_key()")
        op.execute("DROP FUNCTION gridoracle_assign_identity_key()")
    else:
        with op.batch_alter_table("entity_aliases") as batch:
            batch.drop_constraint("uq_entity_alias_provider_from", type_="unique")
        for table, column, _prefix in _IDENTITY_TABLES:
            op.execute(f"DROP TRIGGER trg_{table}_{column}")
