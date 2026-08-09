# VerityGraph AI deployment and sharing

This runbook covers four supported ways to use VerityGraph AI:

1. local single-machine use;
2. LAN sharing inside a trusted network;
3. a temporary public demo tunnel;
4. a persistent HTTPS deployment on a server with a domain.

The core app uses the same architecture in every mode:

```text
Browser
  |
  v
Frontend Nginx
  |  /api/*
  v
FastAPI
  |
  v
SQLite persistent store
```

In production, Caddy sits in front of the frontend and terminates HTTPS. The browser still talks to `/api/...` on the same origin; the backend is not published directly to the internet.

## 1. Fastest local launch with Docker

Requirements:

- Git
- Docker Desktop on Windows/macOS, or Docker Engine + Compose plugin on Linux

Clone the repository and enter it:

```bash
git clone https://github.com/mohit231007/veritygraph-ai.git
cd veritygraph-ai
```

### Windows PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1
```

### macOS / Linux

```bash
chmod +x scripts/start-local.sh
./scripts/start-local.sh
```

Or use Docker Compose directly:

```bash
docker compose up -d --build
```

Open:

- App: `http://localhost:3000`
- Backend health: `http://localhost:8000/api/v1/health`
- FastAPI docs: `http://localhost:8000/docs`

Useful operations:

```bash
# Follow logs
docker compose logs -f

# Stop without deleting SQLite data
docker compose down

# Start again
docker compose up -d
```

Do not use `docker compose down --volumes` unless you intentionally want to delete the local Docker data volume.

## 2. Developer hot-reload mode

Run the backend in one terminal:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_sm
uvicorn app.main:app --app-dir backend --reload
```

Run the frontend in another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the local FastAPI process on port 8000.

## 3. Share on a trusted LAN

The Docker frontend is published on host port 3000. On the same Wi-Fi/LAN, another device can normally reach:

```text
http://<your-computer-LAN-IP>:3000
```

Example:

```text
http://192.168.1.25:3000
```

You may need to allow inbound TCP port 3000 in the host firewall. This mode has no application login, so use it only on a network you trust.

## 4. Temporary public demo with Cloudflare Quick Tunnel

This is convenient for a short recruiter/client/friend demo when the app is already running locally.

Install `cloudflared`, then run:

### Windows

```powershell
.\scripts\share-quick.ps1
```

### macOS / Linux

```bash
chmod +x scripts/share-quick.sh
./scripts/share-quick.sh
```

The terminal prints a temporary `trycloudflare.com` HTTPS URL. Keep the tunnel process running while the demo is in use.

Quick Tunnels are for testing/development, not the durable production hosting path. They also expose the same shared-workspace UI, so do not use this for sensitive material unless you add an appropriate access-control layer in front of it.

## 5. Persistent production HTTPS on a VPS/server

Recommended baseline server:

- current Ubuntu LTS or another maintained Linux distribution;
- Docker Engine + Compose plugin;
- a public IPv4/IPv6 address;
- a domain or subdomain you control;
- inbound TCP ports 80 and 443 open (and UDP 443 if you want HTTP/3).

A modest CPU-only VM is sufficient for the current deterministic ingestion/NLP/retrieval stack for demo and light team workloads. Size CPU/RAM/disk upward for large documents or concurrent users.

### DNS

Create an `A` record (and optionally `AAAA`) such as:

```text
veritygraph.example.com -> YOUR_SERVER_IP
```

Wait until public DNS resolves to the server.

### Server setup

Clone the repository:

```bash
git clone https://github.com/mohit231007/veritygraph-ai.git
cd veritygraph-ai
```

Create the production env file:

```bash
cp .env.production.example .env.production
```

Edit `.env.production`:

```dotenv
VERITYGRAPH_DOMAIN=veritygraph.example.com
VERITYGRAPH_CADDYFILE=./deploy/Caddyfile
VERITYGRAPH_WIKIPEDIA_PROVIDER=live
VERITYGRAPH_WEB_PROVIDER=live
```

Deploy:

```bash
chmod +x scripts/deploy-prod.sh
./scripts/deploy-prod.sh .env.production
```

Or directly:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml config
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Caddy obtains and renews the public TLS certificate when the domain resolves to the server and ports 80/443 are reachable.

Open:

```text
https://veritygraph.example.com
```

The production Compose file exposes only Caddy publicly. Frontend Nginx and FastAPI are internal Compose services. SQLite is stored in the named `veritygraph_data` volume; Caddy certificate state is stored in its own persistent volumes.

## 6. Password-protected shared demo

VerityGraph does not yet have application-level user accounts/RBAC. For a private portfolio/client demo, use the protected Caddy configuration as an outer access gate.

Generate a Caddy-compatible password hash on the server:

```bash
docker run --rm caddy:2-alpine caddy hash-password --plaintext 'choose-a-strong-demo-password'
```

Edit `.env.production`:

```dotenv
VERITYGRAPH_DOMAIN=veritygraph.example.com
VERITYGRAPH_CADDYFILE=./deploy/Caddyfile.protected
VERITYGRAPH_AUTH_USER=demo
VERITYGRAPH_AUTH_PASSWORD_HASH='$2a$14$PASTE_GENERATED_HASH_HERE'
```

Keep the hash single-quoted in the env file so `$` characters are literal.

Redeploy:

```bash
./scripts/deploy-prod.sh .env.production
```

This creates one reverse-proxy username/password gate. It is useful for controlled demos, but it is **not** per-user authorization, workspace isolation, audit identity, or RBAC.

## 7. Back up SQLite safely

The backend image includes `scripts/sqlite_backup.py`, which uses SQLite's backup API instead of copying a live database file byte-for-byte.

Production Compose defines a separate `backup` service under the `ops` profile. The normal API service continues to run as the non-root `veritygraph` user; only this explicitly invoked administrative container runs with the privileges needed to write the host `./backups` bind mount.

Create a backup while the app is running:

```bash
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
docker compose --env-file .env.production -f docker-compose.prod.yml --profile ops run --rm backup \
  backup \
  --source /data/veritygraph.db \
  --output /backups/veritygraph-$STAMP.db
```

The resulting file appears under the server's `backups/` directory. Copy backups off the server to separate storage according to your retention policy.

### Restore

Restoring rewrites the live database, so stop application writers first:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml stop backend frontend
```

Restore a selected backup through the one-off ops service:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml --profile ops run --rm backup \
  restore \
  --source /backups/veritygraph-YYYYMMDDTHHMMSSZ.db \
  --output /data/veritygraph.db
```

Start services again:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

Verify the health endpoint and open a known workspace after every restore.

## 8. Upgrade a deployed server

Back up first, then:

```bash
git pull --ff-only
docker compose --env-file .env.production -f docker-compose.prod.yml build --pull
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

Inspect:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=200 backend frontend caddy
```

## 9. Operational security boundary

The current deployment has:

- HTTPS at the production edge;
- same-origin frontend/API routing;
- no direct public FastAPI port in production Compose;
- non-root backend runtime container;
- isolated one-off administrative backup/restore service;
- bounded upload size;
- SSRF-aware public URL ingestion;
- persistent SQLite storage;
- optional outer Basic Auth for a protected demo;
- explicit backup/restore tooling.

It does **not** yet provide:

- application user registration/login;
- per-user or per-team workspaces;
- role-based permissions;
- per-user audit identity;
- quotas/rate limits suitable for an untrusted public SaaS;
- horizontal multi-instance database coordination.

Therefore the production stack is appropriate for a single-owner deployment, portfolio/client demo, trusted small team, or password-gated shared research environment. Before turning it into an open multi-tenant SaaS, add application identity/RBAC, rate limiting, abuse controls, secrets management, monitoring/alerting, and a multi-user database architecture.

## 10. Production health checklist

Before sharing a durable URL:

```text
[ ] DNS resolves to the server
[ ] HTTPS loads without certificate warnings
[ ] /api/v1/health reports healthy through the public domain
[ ] create workspace works
[ ] upload TXT/PDF/DOCX works
[ ] Wikipedia import works if enabled
[ ] public URL import works if enabled
[ ] retrieval preview works
[ ] grounded evidence pack works
[ ] retrieval evaluation endpoint works
[ ] browser reload preserves workspace data
[ ] ops-profile backup command creates a restorable SQLite file
[ ] protected demo mode enabled when content should not be public
```
