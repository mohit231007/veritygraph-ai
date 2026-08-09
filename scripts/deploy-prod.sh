#!/usr/bin/env sh
set -eu

ENV_FILE="${1:-.env.production}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or is not on PATH." >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Copy .env.production.example and set VERITYGRAPH_DOMAIN first." >&2
  exit 1
fi

mkdir -p backups

echo "Validating production Compose configuration..."
docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml config >/dev/null

echo "Building and starting VerityGraph AI production stack..."
docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml up -d --build

echo
echo "Deployment started. Caddy will serve HTTPS once DNS points at this server and ports 80/443 are reachable."
echo "Check status: docker compose --env-file $ENV_FILE -f docker-compose.prod.yml ps"
echo "Follow logs:  docker compose --env-file $ENV_FILE -f docker-compose.prod.yml logs -f"
