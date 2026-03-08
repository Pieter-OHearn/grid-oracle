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

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose

### Setup

1. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

2. Start all services:

   ```bash
   docker-compose up --build
   ```

3. Access the services:

   - **Dashboard:** http://localhost:3000
   - **API:** http://localhost:8000
   - **API docs:** http://localhost:8000/docs

### Stopping

```bash
docker-compose down
```

To also remove the database volume:

```bash
docker-compose down -v
```

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
