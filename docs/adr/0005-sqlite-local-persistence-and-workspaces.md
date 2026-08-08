# ADR 0005: Use SQLite as the default local persistence and workspace store

- Status: Accepted
- Date: 2026-08-09

## Context

VerityGraph has three ingestion paths producing canonical `SourceDocument` / `SourceSpan` data. Keeping those objects only in process memory makes multi-source research fragile: restarting the backend loses source identity, browser reloads cannot reconstruct collections, and future NLP/graph analysis would have no durable corpus boundary.

The core product must remain free and runnable without hosted infrastructure.

## Decision

SQLite is the default persistent store for canonical source metadata, source spans, research workspaces, and workspace/source membership.

The implementation remains behind repository contracts:

```text
SourceRepository
    +-- SqliteSourceRepository      (default)
    +-- InMemorySourceRepository    (focused tests/experiments)

WorkspaceRepository
    +-- SqliteWorkspaceRepository   (default)
```

The database path is configurable with:

```text
VERITYGRAPH_DATABASE_PATH=data/veritygraph.db
```

Docker runs the database under `/data/veritygraph.db` backed by a named local volume.

## Source schema

`source_id` remains the durable application identifier. Source metadata is stored once and evidence spans reference it with a foreign key using `ON DELETE CASCADE`.

Indexes cover source creation time, content hash, and source-span order.

## Workspace schema

A workspace is metadata plus a many-to-many membership table:

```text
workspaces
    |
    +-- workspace_sources --+--> sources
```

Adding the same source twice is idempotent through the composite primary key `(workspace_id, source_id)`.

Removing a source from a workspace does not delete the source. Deleting a workspace does not delete canonical sources. Deleting a source does cascade its membership rows so workspaces cannot retain orphan references.

## Concurrency and durability

SQLite connections are short-lived per repository operation, foreign keys are enabled on each connection, and the source database enables WAL mode. Mutating operations are guarded by a process-level lock in addition to SQLite's transaction handling.

This is appropriate for the local/single-node product target. A future PostgreSQL adapter can implement the same repository contracts when multi-user/server-scale concurrency becomes a requirement.

## Container posture

The backend image runs as a dedicated non-root `veritygraph` user. `/data` is owned by that user and mounted as a named volume.

## QA

Persistence is tested at two levels:

1. Repository tests create a SQLite file, write source/workspace data, destroy repository objects, instantiate new repository objects over the same file, and verify records are restored.
2. Playwright creates a workspace, imports a source through the browser, adds it to the workspace, reloads the page, and verifies the workspace/source collection remains visible through the real containerized API.

## Consequences

### Positive

- zero hosted-database cost;
- durable source IDs and evidence spans;
- persistent multi-source workspaces;
- reproducible local research sessions;
- storage abstraction remains replaceable;
- database behavior is exercised in E2E instead of being mocked away.

### Trade-offs

- SQLite is a single-node store, not the final choice for high-concurrency multi-user deployments;
- schema migrations will need a formal migration tool before long-lived production upgrades;
- the current repository does not yet deduplicate sources automatically by content hash because provenance imports may intentionally represent separate source events.
