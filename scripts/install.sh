#!/usr/bin/env bash
set -euo pipefail

# OpenSOAR One-Click Install Script
# Usage: curl -fsSL https://raw.githubusercontent.com/opensoar-hq/opensoar-core/main/scripts/install.sh | bash

OPENSOAR_DIR="${OPENSOAR_DIR:-opensoar}"
REPO_URL="https://github.com/opensoar-hq/opensoar-deploy.git"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[opensoar]${NC} $*"; }
warn()  { echo -e "${YELLOW}[opensoar]${NC} $*"; }
error() { echo -e "${RED}[opensoar]${NC} $*" >&2; exit 1; }

# --- Prerequisites ---
command -v docker >/dev/null 2>&1 || error "Docker is not installed. Install it from https://docs.docker.com/get-docker/"
docker compose version >/dev/null 2>&1 || error "Docker Compose v2 is required. Update Docker or install the compose plugin."
docker info >/dev/null 2>&1 || error "Docker daemon is not running. Start Docker and try again."

info "Prerequisites OK (docker + docker compose)"

# --- Clone or update deploy repo ---
if [ -d "$OPENSOAR_DIR" ]; then
  warn "Directory '$OPENSOAR_DIR' already exists — updating"
  cd "$OPENSOAR_DIR"
  git pull --ff-only 2>/dev/null || warn "Could not pull updates (non-fatal)"
else
  info "Cloning opensoar-deploy..."
  git clone --depth 1 "$REPO_URL" "$OPENSOAR_DIR"
  cd "$OPENSOAR_DIR"
fi

# --- Generate .env if missing ---
if [ ! -f .env ]; then
  info "Generating .env with random secrets..."
  JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | od -An -tx1 | tr -d ' \n')
  API_KEY_SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | od -An -tx1 | tr -d ' \n')
  PG_PASSWORD=$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')

  cat > .env <<EOF
POSTGRES_PASSWORD=${PG_PASSWORD}
JWT_SECRET=${JWT_SECRET}
API_KEY_SECRET=${API_KEY_SECRET}
API_PORT=8000
UI_PORT=3000
EOF
  info ".env created with generated secrets"
else
  info "Using existing .env"
fi

# --- Pull images and start ---
info "Pulling latest images..."
docker compose pull

info "Starting OpenSOAR..."
docker compose up -d

# --- Wait for API health ---
info "Waiting for API to become healthy..."
API_PORT=$(grep -oP 'API_PORT=\K\d+' .env 2>/dev/null || echo "8000")
RETRIES=30
until curl -sf "http://localhost:${API_PORT}/api/v1/health" >/dev/null 2>&1; do
  RETRIES=$((RETRIES - 1))
  if [ "$RETRIES" -le 0 ]; then
    warn "API not responding yet — it may still be starting. Check: docker compose logs api"
    break
  fi
  sleep 2
done

if [ "$RETRIES" -gt 0 ]; then
  info "API is healthy!"
fi

UI_PORT=$(grep -oP 'UI_PORT=\K\d+' .env 2>/dev/null || echo "3000")

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  OpenSOAR is running!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  UI:  http://localhost:${UI_PORT}"
echo -e "  API: http://localhost:${API_PORT}/api/v1/health"
echo ""
echo -e "  Logs:    docker compose logs -f"
echo -e "  Stop:    docker compose down"
echo -e "  Update:  docker compose pull && docker compose up -d"
echo ""
