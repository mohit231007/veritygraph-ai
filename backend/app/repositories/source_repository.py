from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Protocol

from app.core.config import get_settings
from app.domain.source import (
    SourceBundle,
    SourceDocument,
    SourceReference,
    SourceSpan,
    SourceType,
)


class SourceRepository(Protocol):
    def save(self, bundle: SourceBundle) -> SourceBundle: ...

    def get(self, source_id: str) -> SourceBundle | None: ...

    def list_documents(self, limit: int = 100) -> list[SourceDocument]: ...

    def clear(self) -> None: ...


class InMemorySourceRepository:
    """Small dependency-free adapter retained for focused tests and experiments."""

    def __init__(self) -> None:
        self._items: dict[str, SourceBundle] = {}
        self._lock = RLock()

    def save(self, bundle: SourceBundle) -> SourceBundle:
        with self._lock:
            self._items[bundle.document.source_id] = bundle
        return bundle

    def get(self, source_id: str) -> SourceBundle | None:
        with self._lock:
            return self._items.get(source_id)

    def list_documents(self, limit: int = 100) -> list[SourceDocument]:
        with self._lock:
            bundles = sorted(
                self._items.values(),
                key=lambda item: item.document.created_at,
                reverse=True,
            )
        return [bundle.document for bundle in bundles[:limit]]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


class SqliteSourceRepository:
    """Persistent local source repository backed by Python's standard-library SQLite."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    source_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    filename TEXT,
                    url TEXT,
                    source_format TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_sources_created_at
                    ON sources(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_sources_content_hash
                    ON sources(content_hash);

                CREATE TABLE IF NOT EXISTS source_spans (
                    span_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    page_number INTEGER,
                    section TEXT,
                    paragraph_number INTEGER,
                    char_start INTEGER NOT NULL CHECK (char_start >= 0),
                    char_end INTEGER NOT NULL CHECK (char_end >= char_start),
                    FOREIGN KEY(source_id) REFERENCES sources(source_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_source_spans_source_order
                    ON source_spans(source_id, char_start, span_id);

                CREATE TABLE IF NOT EXISTS source_references (
                    reference_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    span_id TEXT,
                    page_number INTEGER,
                    paragraph_number INTEGER,
                    target_url TEXT NOT NULL,
                    normalized_target_url TEXT NOT NULL,
                    anchor_text TEXT,
                    context_text TEXT,
                    reference_text TEXT,
                    citation_label TEXT,
                    citation_marker TEXT,
                    extraction_method TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES sources(source_id) ON DELETE CASCADE,
                    FOREIGN KEY(span_id) REFERENCES source_spans(span_id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_source_references_source
                    ON source_references(source_id, reference_id);
                CREATE INDEX IF NOT EXISTS idx_source_references_target
                    ON source_references(normalized_target_url);
                """
            )
            self._ensure_reference_columns(connection)

    @staticmethod
    def _ensure_reference_columns(connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(source_references)").fetchall()
        }
        if "page_number" not in columns:
            connection.execute("ALTER TABLE source_references ADD COLUMN page_number INTEGER")
        if "paragraph_number" not in columns:
            connection.execute(
                "ALTER TABLE source_references ADD COLUMN paragraph_number INTEGER"
            )
        if "reference_text" not in columns:
            connection.execute("ALTER TABLE source_references ADD COLUMN reference_text TEXT")
        if "citation_label" not in columns:
            connection.execute("ALTER TABLE source_references ADD COLUMN citation_label TEXT")
        if "citation_marker" not in columns:
            connection.execute("ALTER TABLE source_references ADD COLUMN citation_marker TEXT")

    def save(self, bundle: SourceBundle) -> SourceBundle:
        document = bundle.document
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sources (
                    source_id, source_type, title, filename, url, source_format,
                    mime_type, content_hash, size_bytes, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    source_type = excluded.source_type,
                    title = excluded.title,
                    filename = excluded.filename,
                    url = excluded.url,
                    source_format = excluded.source_format,
                    mime_type = excluded.mime_type,
                    content_hash = excluded.content_hash,
                    size_bytes = excluded.size_bytes,
                    created_at = excluded.created_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    document.source_id,
                    document.source_type.value,
                    document.title,
                    document.filename,
                    document.url,
                    document.source_format,
                    document.mime_type,
                    document.content_hash,
                    document.size_bytes,
                    document.created_at.isoformat(),
                    json.dumps(document.metadata, sort_keys=True),
                ),
            )
            connection.execute(
                "DELETE FROM source_references WHERE source_id = ?",
                (document.source_id,),
            )
            connection.execute(
                "DELETE FROM source_spans WHERE source_id = ?",
                (document.source_id,),
            )
            connection.executemany(
                """
                INSERT INTO source_spans (
                    span_id, source_id, text, page_number, section,
                    paragraph_number, char_start, char_end
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        span.span_id,
                        span.source_id,
                        span.text,
                        span.page_number,
                        span.section,
                        span.paragraph_number,
                        span.char_start,
                        span.char_end,
                    )
                    for span in bundle.spans
                ],
            )
            connection.executemany(
                """
                INSERT INTO source_references (
                    reference_id, source_id, span_id, page_number, paragraph_number,
                    target_url, normalized_target_url, anchor_text, context_text,
                    reference_text, citation_label, citation_marker, extraction_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        reference.reference_id,
                        reference.source_id,
                        reference.span_id,
                        reference.page_number,
                        reference.paragraph_number,
                        reference.target_url,
                        reference.normalized_target_url,
                        reference.anchor_text,
                        reference.context_text,
                        reference.reference_text,
                        reference.citation_label,
                        reference.citation_marker,
                        reference.extraction_method,
                    )
                    for reference in bundle.references
                ],
            )
        return bundle

    def get(self, source_id: str) -> SourceBundle | None:
        with self._connect() as connection:
            source_row = connection.execute(
                "SELECT * FROM sources WHERE source_id = ?",
                (source_id,),
            ).fetchone()
            if source_row is None:
                return None
            span_rows = connection.execute(
                """
                SELECT * FROM source_spans
                WHERE source_id = ?
                ORDER BY char_start ASC, span_id ASC
                """,
                (source_id,),
            ).fetchall()
            reference_rows = connection.execute(
                """
                SELECT * FROM source_references
                WHERE source_id = ?
                ORDER BY COALESCE(span_id, ''), normalized_target_url, reference_id
                """,
                (source_id,),
            ).fetchall()

        return SourceBundle(
            document=self._document_from_row(source_row),
            spans=[self._span_from_row(row) for row in span_rows],
            references=[self._reference_from_row(row) for row in reference_rows],
        )

    def list_documents(self, limit: int = 100) -> list[SourceDocument]:
        safe_limit = max(1, min(limit, 500))
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM sources ORDER BY created_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [self._document_from_row(row) for row in rows]

    def clear(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM sources")

    @staticmethod
    def _document_from_row(row: sqlite3.Row) -> SourceDocument:
        return SourceDocument(
            source_id=row["source_id"],
            source_type=SourceType(row["source_type"]),
            title=row["title"],
            filename=row["filename"],
            url=row["url"],
            source_format=row["source_format"],
            mime_type=row["mime_type"],
            content_hash=row["content_hash"],
            size_bytes=row["size_bytes"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata_json"]),
        )

    @staticmethod
    def _span_from_row(row: sqlite3.Row) -> SourceSpan:
        return SourceSpan(
            span_id=row["span_id"],
            source_id=row["source_id"],
            text=row["text"],
            page_number=row["page_number"],
            section=row["section"],
            paragraph_number=row["paragraph_number"],
            char_start=row["char_start"],
            char_end=row["char_end"],
        )

    @staticmethod
    def _reference_from_row(row: sqlite3.Row) -> SourceReference:
        return SourceReference(
            reference_id=row["reference_id"],
            source_id=row["source_id"],
            span_id=row["span_id"],
            page_number=row["page_number"],
            paragraph_number=row["paragraph_number"],
            target_url=row["target_url"],
            normalized_target_url=row["normalized_target_url"],
            anchor_text=row["anchor_text"],
            context_text=row["context_text"],
            reference_text=row["reference_text"],
            citation_label=row["citation_label"],
            citation_marker=row["citation_marker"],
            extraction_method=row["extraction_method"],
        )


@lru_cache
def get_source_repository() -> SourceRepository:
    return SqliteSourceRepository(get_settings().database_path)
