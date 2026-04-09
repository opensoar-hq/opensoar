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

# Reinstall after copying the source tree so the runtime package in
# site-packages stays aligned with the current checkout.
RUN uv pip install --system --reinstall .

# Create non-root user for running services
RUN groupadd -r opensoar && useradd -r -g opensoar -d /app -s /sbin/nologin opensoar \
    && chown -R opensoar:opensoar /app

# ── Target: API server ──────────────────────────────────────
FROM base AS api
USER opensoar
EXPOSE 8000
CMD ["uvicorn", "opensoar.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Target: Celery worker ───────────────────────────────────
FROM base AS worker
USER opensoar
CMD ["celery", "-A", "opensoar.worker.celery_app", "worker", "--loglevel=info", "--concurrency=4"]

# ── Target: Database migration ──────────────────────────────
FROM base AS migrate
USER opensoar
CMD ["alembic", "upgrade", "head"]

# ── Target: UI (React dashboard) ─────────────────────────────
FROM node:20-alpine AS ui-build
WORKDIR /app
COPY ui/package*.json ./
RUN npm ci --legacy-peer-deps
COPY ui/ .
RUN npm run build

FROM nginx:alpine AS ui
COPY --from=ui-build /app/dist /usr/share/nginx/html
COPY ui/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
