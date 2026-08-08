from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Protocol
from uuid import uuid4

from app.core.config import get_settings
from app.domain.workspace import WorkspaceCreate, WorkspaceDetail, WorkspaceSummary
from app.repositories.source_repository import SourceRepository, get_source_repository


class WorkspaceNotFoundError(KeyError):
    pass


class WorkspaceSourceNotFoundError(KeyError):
    pass


class WorkspaceRepository(Protocol):
    def create(self, request: WorkspaceCreate) -> WorkspaceDetail: ...

    def list(self) -> list[WorkspaceSummary]: ...

    def get(self, workspace_id: str) -> WorkspaceDetail | None: ...

    def add_source(self, workspace_id: str, source_id: str) -> WorkspaceDetail: ...

    def remove_source(self, workspace_id: str, source_id: str) -> WorkspaceDetail: ...

    def delete(self, workspace_id: str) -> bool: ...

    def clear(self) -> None: ...


class SqliteWorkspaceRepository:
    """Persistent multi-source workspaces stored alongside canonical source records."""

    def __init__(
        self,
        database_path: str | Path,
        source_repository: SourceRepository,
    ) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.source_repository = source_repository
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_workspaces_updated_at
                    ON workspaces(updated_at DESC);

                CREATE TABLE IF NOT EXISTS workspace_sources (
                    workspace_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    added_at TEXT NOT NULL,
                    PRIMARY KEY(workspace_id, source_id),
                    FOREIGN KEY(workspace_id)
                        REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
                    FOREIGN KEY(source_id)
                        REFERENCES sources(source_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_workspace_sources_added
                    ON workspace_sources(workspace_id, added_at, source_id);
                """
            )

    def create(self, request: WorkspaceCreate) -> WorkspaceDetail:
        now = datetime.now(UTC)
        workspace_id = f"ws_{uuid4().hex}"
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspaces (
                    workspace_id, name, description, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    workspace_id,
                    request.name,
                    request.description,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        return WorkspaceDetail(
            workspace_id=workspace_id,
            name=request.name,
            description=request.description,
            created_at=now,
            updated_at=now,
            source_count=0,
            sources=[],
        )

    def list(self) -> list[WorkspaceSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    w.workspace_id,
                    w.name,
                    w.description,
                    w.created_at,
                    w.updated_at,
                    COUNT(ws.source_id) AS source_count
                FROM workspaces AS w
                LEFT JOIN workspace_sources AS ws
                    ON ws.workspace_id = w.workspace_id
                GROUP BY w.workspace_id
                ORDER BY w.updated_at DESC, w.created_at DESC
                """
            ).fetchall()
        return [self._summary_from_row(row) for row in rows]

    def get(self, workspace_id: str) -> WorkspaceDetail | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    w.workspace_id,
                    w.name,
                    w.description,
                    w.created_at,
                    w.updated_at,
                    COUNT(ws.source_id) AS source_count
                FROM workspaces AS w
                LEFT JOIN workspace_sources AS ws
                    ON ws.workspace_id = w.workspace_id
                WHERE w.workspace_id = ?
                GROUP BY w.workspace_id
                """,
                (workspace_id,),
            ).fetchone()
            if row is None:
                return None
            source_rows = connection.execute(
                """
                SELECT source_id
                FROM workspace_sources
                WHERE workspace_id = ?
                ORDER BY added_at ASC, source_id ASC
                """,
                (workspace_id,),
            ).fetchall()

        documents = []
        for source_row in source_rows:
            bundle = self.source_repository.get(source_row["source_id"])
            if bundle is not None:
                documents.append(bundle.document)

        summary = self._summary_from_row(row)
        return WorkspaceDetail(**summary.model_dump(), sources=documents)

    def add_source(self, workspace_id: str, source_id: str) -> WorkspaceDetail:
        if self.get(workspace_id) is None:
            raise WorkspaceNotFoundError(workspace_id)
        if self.source_repository.get(source_id) is None:
            raise WorkspaceSourceNotFoundError(source_id)

        now = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO workspace_sources (
                    workspace_id, source_id, added_at
                ) VALUES (?, ?, ?)
                """,
                (workspace_id, source_id, now),
            )
            connection.execute(
                "UPDATE workspaces SET updated_at = ? WHERE workspace_id = ?",
                (now, workspace_id),
            )

        detail = self.get(workspace_id)
        if detail is None:  # defensive against external deletion between operations
            raise WorkspaceNotFoundError(workspace_id)
        return detail

    def remove_source(self, workspace_id: str, source_id: str) -> WorkspaceDetail:
        if self.get(workspace_id) is None:
            raise WorkspaceNotFoundError(workspace_id)

        now = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                "DELETE FROM workspace_sources WHERE workspace_id = ? AND source_id = ?",
                (workspace_id, source_id),
            )
            connection.execute(
                "UPDATE workspaces SET updated_at = ? WHERE workspace_id = ?",
                (now, workspace_id),
            )

        detail = self.get(workspace_id)
        if detail is None:
            raise WorkspaceNotFoundError(workspace_id)
        return detail

    def delete(self, workspace_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM workspaces WHERE workspace_id = ?",
                (workspace_id,),
            )
        return cursor.rowcount > 0

    def clear(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM workspaces")

    @staticmethod
    def _summary_from_row(row: sqlite3.Row) -> WorkspaceSummary:
        return WorkspaceSummary(
            workspace_id=row["workspace_id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            source_count=row["source_count"],
        )


@lru_cache
def get_workspace_repository() -> WorkspaceRepository:
    settings = get_settings()
    source_repository = get_source_repository()
    return SqliteWorkspaceRepository(settings.database_path, source_repository)
