# Registry index digests/architectures are retained in base-images.json.
FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS dependencies
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.12.19

FROM dependencies AS api_dependencies
RUN uv sync --frozen --no-dev --extra api
FROM dependencies AS worker_dependencies
RUN uv sync --frozen --no-dev --extra pipeline

FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS runtime
RUN groupadd --gid 10001 gridoracle && useradd --uid 10001 --gid 10001 --no-create-home gridoracle
WORKDIR /app
COPY api ./api
COPY gridoracle ./gridoracle
COPY scripts ./scripts
COPY db ./db
COPY alembic.ini ./
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001

FROM runtime AS api
LABEL org.opencontainers.image.description="GridOracle backend API serving published Formula 1 forecasts and provenance."
COPY --from=api_dependencies /app/.venv /app/.venv
ENTRYPOINT ["python", "-m", "gridoracle.ops.runtime"]
CMD ["api"]

FROM runtime AS worker
LABEL org.opencontainers.image.description="GridOracle background worker and scheduler for bounded forecast jobs."
USER root
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY --from=worker_dependencies /app/.venv /app/.venv
COPY pipeline ./pipeline
USER 10001:10001
ENTRYPOINT ["python", "-m", "gridoracle.ops.runtime"]
CMD ["worker"]

FROM oven/bun:1.4.2-debian@sha256:4f6e31d1a54d6a3dd312daef655fc998101b5043d52e12592ac293ef04b9bc73 AS frontend_build
WORKDIR /app
COPY dashboard/package.json dashboard/bun.lock ./
RUN bun install --frozen-lockfile
COPY dashboard ./
RUN bun run build

FROM nginx:1.28.2-alpine@sha256:5b4900b042ccfa8b0a73df622c3a60f2322faeb2be800cbee5aa7b44d241649e AS frontend
LABEL org.opencontainers.image.description="GridOracle web dashboard for Formula 1 forecasts, results and provenance."
COPY deploy/wp13/nginx.conf /etc/nginx/nginx.conf
COPY --from=frontend_build /app/dist /usr/share/nginx/html
USER 101:101
EXPOSE 3000
ENTRYPOINT ["nginx", "-g", "daemon off;"]
