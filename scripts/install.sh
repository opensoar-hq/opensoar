#!/usr/bin/env bash
set -euo pipefail

# OpenSOAR One-Click Install Script
# Usage: curl -fsSL https://opensoar.app/install.sh | sh

OPENSOAR_DIR="${OPENSOAR_DIR:-opensoar}"
BASE_URL="${BASE_URL:-https://raw.githubusercontent.com/opensoar-hq/opensoar-core/main/deploy}"

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
command -v curl >/dev/null 2>&1 || error "curl is required but not installed."

info "Prerequisites OK (docker + docker compose)"

# --- Set up directory ---
mkdir -p "$OPENSOAR_DIR"
cd "$OPENSOAR_DIR"

# --- Download docker-compose.yml ---
if [ -f docker-compose.yml ]; then
  info "Updating docker-compose.yml..."
else
  info "Downloading docker-compose.yml..."
fi
curl -fsSL "$BASE_URL/docker-compose.yml" -o docker-compose.yml

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
if [ "${OPENSOAR_SKIP_PULL:-0}" = "1" ]; then
  info "Skipping image pull (OPENSOAR_SKIP_PULL=1)"
else
  info "Pulling latest images..."
  docker compose pull
fi

info "Starting OpenSOAR..."
docker compose up -d

# --- Wait for API health ---
info "Waiting for API to become healthy..."
read_env_value() {
  local key="$1"
  local default_value="$2"
  local value
  value=$(awk -F= -v key="$key" '$1 == key { print $2; exit }' .env 2>/dev/null || true)
  if [ -n "$value" ]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$default_value"
  fi
}

API_PORT=$(read_env_value "API_PORT" "8000")
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

UI_PORT=$(read_env_value "UI_PORT" "3000")

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
