FROM ghcr.io/astral-sh/uv:0.12.19 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra api

COPY api ./api

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
