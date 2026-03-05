#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="docker-compose.yml"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$PROJECT_DIR"

echo "[build-and-deploy] Using compose file: $COMPOSE_FILE"

echo "[build-and-deploy] Stopping existing compose project (if any)..."
if ! docker compose down --remove-orphans; then
    echo "[build-and-deploy] warning: compose down failed, continuing anyway"
fi

echo "[build-and-deploy] Building and starting containers..."
docker compose -f "$COMPOSE_FILE" up -d --build "$@"

echo "[build-and-deploy] Done. To follow logs run: docker compose logs -f"

exit 0
