import os

# Use an in-memory SQLite DB so tests run without a real Postgres instance.
# Must be set before api.database is imported (engine is created at module level).
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
# Preserve legacy regression tests; public-surface tests use create_app(legacy=False).
os.environ["GRIDORACLE_LEGACY_API"] = "1"
