# ── Base: Python with dependencies ──────────────────────────
FROM python:3.12-slim AS base

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock README.md ./
RUN uv pip install --system .

COPY src/ ./src/
COPY playbooks/ ./playbooks/
COPY migrations/ ./migrations/
COPY alembic.ini ./

RUN uv pip install --system .

# ── Target: API server ──────────────────────────────────────
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "opensoar.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Target: Celery worker ───────────────────────────────────
FROM base AS worker
CMD ["celery", "-A", "opensoar.worker.celery_app", "worker", "--loglevel=info", "--concurrency=4"]

# ── Target: Database migration ──────────────────────────────
FROM base AS migrate
CMD ["alembic", "upgrade", "head"]
