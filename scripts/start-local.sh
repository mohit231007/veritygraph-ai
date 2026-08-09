#!/usr/bin/env sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or is not on PATH." >&2
  exit 1
fi

docker compose version >/dev/null
mkdir -p backups

echo "Building and starting VerityGraph AI..."
docker compose up -d --build

echo
echo "VerityGraph AI is running:"
echo "  App:      http://localhost:3000"
echo "  API:      http://localhost:8000/api/v1/health"
echo "  API docs: http://localhost:8000/docs"
echo
echo "Stop without deleting data: docker compose down"
echo "Follow logs:                docker compose logs -f"
