# GridOracle — Agent Context

## What this project is
GridOracle is a Formula 1 race prediction platform. It uses a machine learning 
model to predict finishing positions for each race, stores predictions, then 
evaluates accuracy after the race completes.

## Monorepo structure
- `api/` — FastAPI backend, serves predictions and results to the dashboard
- `pipeline/` — Data ingestion, feature engineering, ML training and prediction
- `dashboard/` — React frontend
- `db/migrations/` — Numbered SQL migration files

## How to run the project
docker-compose up --build

## How to work on a ticket

When asked to work on a ticket, follow these steps in order:

1. Read the ticket from the GitHub project — get the full title, description, 
   tasks, and acceptance criteria
2. Create a new branch from `main` using the format: `ticket/001-short-description`
3. Complete all tasks listed in the ticket
4. Ensure all acceptance criteria are met before finishing
5. Commit your work with clear commit messages referencing the ticket number
   e.g. `[TICKET 001] Add docker-compose and monorepo scaffold`
6. Raise a pull request to `main` with:
   - Title matching the ticket title
   - Body summarising what was done and how acceptance criteria were met
   - Link to the original GitHub issue
7. Move the ticket to the `Ready for Review` column on the kanban board

## Tech stack
- Database: PostgreSQL 16
- Backend: FastAPI + SQLAlchemy + Pydantic
- Pipeline: Python, FastF1, XGBoost, APScheduler
- Frontend: React + Vite + Tailwind + Recharts
- Infrastructure: Docker + Docker Compose

## Environment variables
See `.env.example` for all required variables. Never hardcode credentials.

## Code conventions
- Python: use type hints, keep functions small and single-purpose
- SQL: all migrations are numbered sequentially e.g. `001_initial_schema.sql`
- API routes return Pydantic models, never raw dicts
- All ingestion scripts support upsert — re-running should never create duplicates

## Data sources
- FastF1 library for historical race and qualifying data
- OpenWeatherMap API for weather forecasts
- Circuit coordinates are stored in the `circuits` table

## Key design rules
- Never reference future data in features (no data leakage)
- Every prediction must be linked to a model_version_id
- Store weather snapshots at prediction time with a captured_at timestamp
