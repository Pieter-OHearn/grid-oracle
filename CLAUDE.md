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

## GitHub project

- **Repo:** `Pieter-OHearn/grid-oracle`
- **Project board:** `GridOracle MVP` (project number **3**, owner `Pieter-OHearn`)
- **Board columns:** Backlog → Ready → In progress → In review → Done
- **Ticket format:** issues titled `TICKET NNN — Short description`

### CLI quick reference
```bash
# List all issues
gh issue list --repo Pieter-OHearn/grid-oracle --state all

# View a specific ticket
gh issue view <number> --repo Pieter-OHearn/grid-oracle --json title,body

# List project board items
gh project item-list 3 --owner Pieter-OHearn --format json

# Add an issue to the board
gh project item-add 3 --owner Pieter-OHearn --url <issue-url>
```

## How to work on a ticket

When asked to work on a ticket, follow these steps in order:

1. Read the ticket from the GitHub project (see CLI reference above) — get the
   full title, description, tasks, and acceptance criteria
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

## Frontend design reference

The `dashboard/design/` directory contains a Figma "Make Code" export of the approved
UI designs. These files are **visual references only** — do NOT copy their file
structure or use the code as-is. The design uses large monolithic page components;
your implementation must be properly componentised with small, reusable files.

Key reference files:
- `dashboard/design/src/app/components/Layout.tsx` — Sidebar + header layout
- `dashboard/design/src/app/pages/PredictionPage.tsx` — Prediction view
- `dashboard/design/src/app/pages/ResultsPage.tsx` — Results comparison view
- `dashboard/design/src/app/pages/DashboardPage.tsx` — Season accuracy dashboard
- `dashboard/design/src/styles/` — Colour palette, fonts, scrollbar styles
- `dashboard/design/src/app/data/mockData.ts` — Data types and mock data structure

Design system summary:
- Dark theme: backgrounds `#08080e`, `#0c0c16`, `#0f0f1a`; borders `#1e1e30`
- Accent colour: `#e10600` (F1 red)
- Fonts: Barlow Condensed (headings/labels), Barlow (body), JetBrains Mono (data)
- Icons: lucide-react; Animations: framer-motion; Charts: recharts

When implementing dashboard tickets (012–015), read the corresponding design file
to match the visual design, then build with properly separated components where no
single component file exceeds ~150 lines.

## Tech stack
- Database: PostgreSQL 16
- Backend: FastAPI + SQLAlchemy + Pydantic
- Pipeline: Python, FastF1, XGBoost, APScheduler
- Frontend: React + Vite + Tailwind + Recharts (package manager: **Bun**)
- Infrastructure: Docker + Docker Compose

## Environment variables
See `.env.example` for all required variables. Never hardcode credentials.

## Code conventions
- Python: use type hints, keep functions small and single-purpose
- SQL: all migrations are numbered sequentially e.g. `001_initial_schema.sql`
- API routes return Pydantic models, never raw dicts
- All ingestion scripts support upsert — re-running should never create duplicates
- Never add `Co-Authored-By` trailers to commit messages

## Before committing

Run these checks and fix any failures before every commit:

```bash
# Lint, format check, and build (frontend — run from dashboard/)
bun run lint
bun run format:check   # if it fails, run: bun run format
bun run build

# Lint and format (pipeline + api)
ruff check pipeline/ api/
ruff format --check pipeline/ api/

# Tests (pipeline)
python -m pytest pipeline/tests/ -v
```

All checks must pass cleanly. If `ruff format --check` fails, run `ruff format pipeline/ api/` to auto-fix. If `bun run format:check` fails, run `bun run format` to auto-fix. Re-stage any reformatted files before committing.

## Data sources
- FastF1 library for historical race and qualifying data
- OpenWeatherMap API for weather forecasts
- Circuit coordinates are stored in the `circuits` table

## Key design rules
- Never reference future data in features (no data leakage)
- Every prediction must be linked to a model_version_id
- Store weather snapshots at prediction time with a captured_at timestamp

## META — Maintaining this document

### When to update this file
Proactively suggest updates to CLAUDE.md when:
- You make a mistake and are corrected — ask: "Should I add a rule to prevent this?"
- A new pattern or convention is introduced — ask: "Should I document this?"
- You ask about the same thing multiple times — suggest: "I keep asking about [X], should I add a rule?"

### How to write good rules
When adding new rules, follow these principles:
- Be specific: describe the exact situation and what to do
- Be concise: one clear sentence is better than a paragraph
- Include the "why" only if it's non-obvious
- Group related rules together under existing headings
- Never add redundant rules that duplicate existing ones
- After adding a rule to a section, update the summary at the top of this file
