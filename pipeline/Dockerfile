FROM ghcr.io/astral-sh/uv:0.12.19 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra pipeline

COPY pipeline ./pipeline

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "pipeline.scheduler"]
