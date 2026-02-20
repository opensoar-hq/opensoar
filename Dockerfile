# ── Stage 1: Build UI ────────────────────────────────────────
FROM node:22-alpine AS ui-build

WORKDIR /app/ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --legacy-peer-deps
COPY ui/ .
RUN npm run build

# ── Stage 2: Python app ─────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml ./
RUN uv pip install --system . 2>/dev/null || true

COPY . .
RUN uv pip install --system .

# Copy built UI into static directory
COPY --from=ui-build /app/ui/dist /app/static

CMD ["uvicorn", "opensoar.main:app", "--host", "0.0.0.0", "--port", "8000"]
