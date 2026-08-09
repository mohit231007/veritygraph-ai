#!/usr/bin/env sh
set -eu

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed or is not on PATH." >&2
  exit 1
fi

if ! curl --fail --silent http://localhost:3000 >/dev/null; then
  echo "VerityGraph is not reachable at http://localhost:3000. Run ./scripts/start-local.sh first." >&2
  exit 1
fi

echo "Opening a temporary Cloudflare Quick Tunnel to the local VerityGraph frontend."
echo "The public URL will be printed below. Keep this terminal open while sharing it."
cloudflared tunnel --url http://localhost:3000
