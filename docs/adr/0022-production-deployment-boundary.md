# ADR 0022: Same-origin production deployment and current access boundary

## Status

Accepted for the 0.9 production-deployable beta.

## Context

The local application already uses a useful boundary:

```text
browser -> frontend Nginx -> /api proxy -> FastAPI -> SQLite
```

A public deployment should preserve that topology rather than expose FastAPI directly or require a separate browser-visible API hostname. It also needs HTTPS, persistent certificate state, persistent SQLite state, restart policies, backups and an explicit answer to who can access destructive workspace actions.

## Decision

Production Docker Compose adds Caddy as the only internet-facing service:

```text
Internet
  |
  | HTTPS 443 / HTTP 80 redirect
  v
Caddy
  |
  v
Frontend Nginx
  |  /api/*
  v
FastAPI
  |
  v
named SQLite volume
```

Caddy owns public TLS and security response headers. Frontend and backend services use Compose-internal networking only. The browser continues to use relative `/api/v1/...` URLs, so the UI and API remain same-origin.

Caddy data/config volumes are persistent so certificate state survives container recreation.

## Access modes

### Public/shared workspace

`deploy/Caddyfile` exposes the application to anyone who can reach the URL. This is appropriate only when the workspace is intentionally public/shared.

### Password-gated demo

`deploy/Caddyfile.protected` adds Caddy Basic Auth before the frontend. This is an outer shared credential gate suitable for a recruiter, client or trusted small-team demonstration.

It is not application identity. It does not provide:

- per-user accounts;
- per-workspace ownership;
- role-based authorization;
- identity-aware audit logs;
- tenant isolation.

## Persistence

SQLite remains the application truth store for the current single-instance architecture. Production Compose stores `/data/veritygraph.db` in a named Docker volume.

`./backups` is bind-mounted as `/backups`. `scripts/sqlite_backup.py` uses SQLite's backup API to create a consistent backup while the application is live. Restore requires stopping writers first.

## Public URL ingestion

Application-level SSRF controls remain in force in production. These controls do not replace infrastructure egress policy. A hardened deployment should additionally restrict container/network egress according to organizational requirements.

## Scaling boundary

The 0.9 deployment intentionally runs a single FastAPI/SQLite writer topology. It is appropriate for:

- a single-owner deployment;
- portfolio or client demos;
- a trusted small team;
- light research workloads.

Before horizontal multi-instance or untrusted multi-tenant SaaS use, migrate the persistence/concurrency boundary and add identity, authorization, quotas, rate limiting, abuse controls and operational monitoring.

## Consequences

### Positive

- one domain and one HTTPS origin for the whole app;
- backend port is not published publicly;
- no browser-side API secrets;
- simple domain migration;
- automatic TLS lifecycle at the edge;
- protected demo mode without changing application code;
- explicit backup/restore path.

### Trade-offs

- Basic Auth is deliberately coarse;
- SQLite limits horizontal scaling;
- Caddy adds one production container;
- a real open SaaS still requires application-level identity/RBAC and stronger operational controls.
