"""Create or update the deployment's database roles from its URL secrets.

A reviewed operator one-off, run as the administrator (the migration URL);
serving never creates roles. The API reader gets SELECT only; the worker gets
SELECT, INSERT and UPDATE (the write-once lineage tables refuse updates on
their own) and the sequences its inserts use. Default privileges extend both
to tables later migrations create. Re-running only resets the passwords.
"""

import argparse
import json
import os
import re
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from gridoracle.ops.runtime import configure

ROLE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
READ = ("SELECT",)
WRITE = ("SELECT", "INSERT", "UPDATE")


def _identity(url: str) -> tuple[str, str]:
    parsed = make_url(url)
    if not parsed.username or not ROLE.fullmatch(parsed.username):
        raise ValueError("role names must be plain lowercase identifiers")
    if not parsed.password:
        raise ValueError("each role URL must carry its password")
    return parsed.username, parsed.password


def apply(engine, roles: list[tuple[str, tuple[str, ...]]]) -> list[str]:
    applied = []
    with engine.begin() as conn:
        admin, database = conn.execute(
            text("SELECT current_user, current_database()")
        ).one()
        for url, privileges in roles:
            name, password = _identity(url)
            if name == admin:
                raise ValueError("an application role cannot be the administrator")
            exists = conn.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname=:name"), {"name": name}
            ).first()
            if not exists:
                conn.exec_driver_sql(f'CREATE ROLE "{name}" LOGIN')
            # psycopg2 quotes the password client-side; it never reaches SQL text.
            conn.exec_driver_sql(
                f'ALTER ROLE "{name}" WITH LOGIN PASSWORD %(password)s',
                {"password": password},
            )
            grants = ", ".join(privileges)
            for statement in (
                f'GRANT CONNECT ON DATABASE "{database}" TO "{name}"',
                f'GRANT USAGE ON SCHEMA public TO "{name}"',
                f'GRANT {grants} ON ALL TABLES IN SCHEMA public TO "{name}"',
                f'ALTER DEFAULT PRIVILEGES FOR ROLE "{admin}" IN SCHEMA public '
                f'GRANT {grants} ON TABLES TO "{name}"',
            ):
                conn.exec_driver_sql(statement)
            if "INSERT" in privileges:
                conn.exec_driver_sql(
                    f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{name}"'
                )
                conn.exec_driver_sql(
                    f'ALTER DEFAULT PRIVILEGES FOR ROLE "{admin}" IN SCHEMA public '
                    f'GRANT USAGE, SELECT ON SEQUENCES TO "{name}"'
                )
            applied.append(name)
    return applied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url-file", type=Path, required=True)
    parser.add_argument("--worker-url-file", type=Path, required=True)
    args = parser.parse_args()
    configure()
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        applied = apply(
            engine,
            [
                (args.api_url_file.read_text().strip(), READ),
                (args.worker_url_file.read_text().strip(), WRITE),
            ],
        )
    finally:
        engine.dispose()
    print(json.dumps({"roles": applied}))


if __name__ == "__main__":
    main()
