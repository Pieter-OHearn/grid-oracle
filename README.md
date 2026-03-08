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
