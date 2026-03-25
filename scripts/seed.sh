#!/bin/bash
set -e

echo "Seeding OpenSOAR with demo data..."
cd "$(dirname "$0")/.."
uv run scripts/seed.py "$@"
