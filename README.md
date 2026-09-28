# GridOracle

Formula 1 race prediction platform. Uses machine learning to predict finishing positions, stores predictions, and evaluates accuracy after each race.

## Project structure

```
api/          — FastAPI backend
pipeline/     — Data ingestion, feature engineering, ML training
dashboard/    — React frontend
db/migrations — SQL migration files
```

## Getting started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose for the
  isolated sample stack.
- Python 3.12 (pinned in `.python-version`) and
  [uv](https://docs.astral.sh/uv/) for local Python work.
- Bun 1.2.5 (pinned in `.bun-version`) for the dashboard.

### Safe sample startup

The default Compose path is intentionally a read-only-in-spirit demo: it
creates a **new `gridoracle_sample_pgdata` volume**, loads only the committed
static fixture in `db/sample/001_static_demo.sql`, and does not start the
pipeline scheduler. It does not call an F1, weather, or other provider.

1. Copy the example environment file and keep the development-only database
   values unless you are intentionally configuring another local environment:

   ```bash
   cp .env.example .env
   ```

2. Start the sample API and dashboard:

   ```bash
   docker compose up --build
   ```

3. Access the services:

   - **Dashboard:** http://localhost:3000
   - **API:** http://localhost:8000
   - **API docs:** http://localhost:8000/docs

The sample is fictional hand-authored data, documented in its SQL header. It
is not training data, forecast evidence, or a substitute for a real migration.

The scheduler is deliberately opt-in and must never be used as a substitute
for the legacy bootstrap. It requires a real local database configuration and
`OPENWEATHER_API_KEY`:

```bash
docker compose --profile scheduler up pipeline
```

Do not run `pipeline.bootstrap` against a real database. Before any future
migration, inventory the existing installation and back it up with the
database owner's approved procedure; WP02 will define the migration ledger.

### Stopping

```bash
docker compose down
```

To also remove the database volume:

```bash
docker compose down -v
```

This removes only the named sample volume created by the default stack. It
does not migrate, backfill, or modify an existing installation.

### Reproducible local dependencies and checks

Install the exact Python dependency graph recorded in `uv.lock` and the Bun
lockfile before running checks:

```bash
uv sync --all-extras --group dev --frozen
cd dashboard && bun install --frozen-lockfile
```

Runtime images install only `api/requirements.txt` or
`pipeline/requirements.txt`; their matching `*-dev.txt` files add test and
lint tools. This keeps serving, training, and local/CI dependencies separate.

Run the complete deterministic local suite (it does not start Compose,
providers, the scheduler, or bootstrap):

```bash
make check
make test
cd dashboard && bun run build
```

### Configuration validation

Validate settings before starting a process. The commands only parse and
validate environment values; they do not connect to a database or provider:

```bash
uv run --extra api --group dev python -m scripts.validate_config --mode api
uv run --extra pipeline --group dev python -m scripts.validate_config --mode pipeline
uv run --extra pipeline --group dev python -m scripts.validate_config --mode scheduler
```

`DATABASE_URL` is required for API and pipeline modes and must use
`postgresql://`, `postgresql+psycopg2://`, or `sqlite://`. Scheduler mode also
requires `OPENWEATHER_API_KEY`. Errors name the missing variable and point to
`.env.example`; the default sample Compose stack supplies its own local values
and never enables scheduler mode.

## Code quality

### Python (api/ and pipeline/)

Linting and formatting is handled by [Ruff](https://docs.astral.sh/ruff/).
Configuration lives in `pyproject.toml` at the repo root.

```bash
# Lint
make lint-py

# Format
make format-py

# Check formatting without modifying files
make check-py
```

### JavaScript / TypeScript (dashboard/)

Linting is handled by [ESLint](https://eslint.org/) with plugins for React,
SonarJS (cognitive complexity), Unicorn, and unused-imports.
Formatting is handled by [Prettier](https://prettier.io/).

```bash
cd dashboard

# Install dependencies (first time)
npm install

# Lint
npm run lint

# Format
npm run format

# Check formatting without modifying files
npm run format:check
```

### Root-level orchestration

Run everything at once from the repo root:

```bash
make lint     # lint Python + JS
make format   # format Python + JS
make check    # check Python + JS without modifying files
```

### Pre-commit hooks (optional)

Install [pre-commit](https://pre-commit.com/) and set up the hooks:

```bash
pip install pre-commit
pre-commit install
```

Hooks will run Ruff, Prettier, and ESLint automatically before each commit.
