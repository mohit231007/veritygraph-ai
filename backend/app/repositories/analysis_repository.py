from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Protocol

from app.core.config import get_settings
from app.domain.analysis import (
    AnalysisRun,
    AnalysisStatus,
    AssertionPolarity,
    Entity,
    EntityMention,
    Relation,
    RelationEvidence,
    WorkspaceAnalysis,
)


class AnalysisRepository(Protocol):
    def save(self, analysis: WorkspaceAnalysis) -> WorkspaceAnalysis: ...

    def get(self, run_id: str) -> WorkspaceAnalysis | None: ...

    def latest_for_workspace(self, workspace_id: str) -> WorkspaceAnalysis | None: ...

    def list_runs(self, workspace_id: str, limit: int = 20) -> list[AnalysisRun]: ...

    def clear(self) -> None: ...


class SqliteAnalysisRepository:
    """Persistent analysis runs with entity/relation/source provenance in local SQLite."""

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
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    run_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    pipeline_version TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    extractor_version TEXT NOT NULL,
                    resolver_version TEXT NOT NULL DEFAULT 'none',
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    duration_ms INTEGER,
                    source_count INTEGER NOT NULL,
                    span_count INTEGER NOT NULL,
                    entity_count INTEGER NOT NULL,
                    relation_count INTEGER NOT NULL,
                    error TEXT,
                    FOREIGN KEY(workspace_id)
                        REFERENCES workspaces(workspace_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_analysis_runs_workspace_started
                    ON analysis_runs(workspace_id, started_at DESC);

                CREATE TABLE IF NOT EXISTS analysis_run_sources (
                    run_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    PRIMARY KEY(run_id, source_id),
                    FOREIGN KEY(run_id) REFERENCES analysis_runs(run_id) ON DELETE CASCADE,
                    FOREIGN KEY(source_id) REFERENCES sources(source_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_analysis_run_sources_run_position
                    ON analysis_run_sources(run_id, position);

                CREATE TABLE IF NOT EXISTS analysis_entities (
                    entity_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    normalized_key TEXT NOT NULL,
                    mention_count INTEGER NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES analysis_runs(run_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_analysis_entities_run_type
                    ON analysis_entities(run_id, entity_type, mention_count DESC);

                CREATE TABLE IF NOT EXISTS analysis_entity_mentions (
                    mention_id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    span_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    start_char INTEGER NOT NULL,
                    end_char INTEGER NOT NULL,
                    FOREIGN KEY(entity_id)
                        REFERENCES analysis_entities(entity_id) ON DELETE CASCADE,
                    FOREIGN KEY(source_id) REFERENCES sources(source_id) ON DELETE CASCADE,
                    FOREIGN KEY(span_id) REFERENCES source_spans(span_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_relations (
                    relation_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    subject_entity_id TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object_entity_id TEXT NOT NULL,
                    polarity TEXT NOT NULL DEFAULT 'unknown',
                    polarity_method TEXT NOT NULL DEFAULT 'historical_unknown',
                    extraction_score REAL NOT NULL,
                    extraction_method TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES analysis_runs(run_id) ON DELETE CASCADE,
                    FOREIGN KEY(subject_entity_id)
                        REFERENCES analysis_entities(entity_id) ON DELETE CASCADE,
                    FOREIGN KEY(object_entity_id)
                        REFERENCES analysis_entities(entity_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_analysis_relations_run
                    ON analysis_relations(run_id, extraction_score DESC);

                CREATE TABLE IF NOT EXISTS analysis_relation_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    relation_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    span_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    sentence_start INTEGER NOT NULL,
                    sentence_end INTEGER NOT NULL,
                    FOREIGN KEY(relation_id)
                        REFERENCES analysis_relations(relation_id) ON DELETE CASCADE,
                    FOREIGN KEY(source_id) REFERENCES sources(source_id) ON DELETE CASCADE,
                    FOREIGN KEY(span_id) REFERENCES source_spans(span_id) ON DELETE CASCADE
                );
                """
            )
            run_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(analysis_runs)").fetchall()
            }
            if "resolver_version" not in run_columns:
                connection.execute(
                    """
                    ALTER TABLE analysis_runs
                    ADD COLUMN resolver_version TEXT NOT NULL DEFAULT 'none'
                    """
                )

            relation_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(analysis_relations)").fetchall()
            }
            if "polarity" not in relation_columns:
                connection.execute(
                    """
                    ALTER TABLE analysis_relations
                    ADD COLUMN polarity TEXT NOT NULL DEFAULT 'unknown'
                    """
                )
            if "polarity_method" not in relation_columns:
                connection.execute(
                    """
                    ALTER TABLE analysis_relations
                    ADD COLUMN polarity_method TEXT NOT NULL DEFAULT 'historical_unknown'
                    """
                )

    def save(self, analysis: WorkspaceAnalysis) -> WorkspaceAnalysis:
        run = analysis.run
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analysis_runs (
                    run_id, workspace_id, status, pipeline_version, model_name,
                    model_version, extractor_version, resolver_version, started_at,
                    completed_at, duration_ms, source_count, span_count, entity_count,
                    relation_count, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    completed_at = excluded.completed_at,
                    duration_ms = excluded.duration_ms,
                    source_count = excluded.source_count,
                    span_count = excluded.span_count,
                    entity_count = excluded.entity_count,
                    relation_count = excluded.relation_count,
                    error = excluded.error
                """,
                (
                    run.run_id,
                    run.workspace_id,
                    run.status.value,
                    run.pipeline_version,
                    run.model_name,
                    run.model_version,
                    run.extractor_version,
                    run.resolver_version,
                    run.started_at.isoformat(),
                    run.completed_at.isoformat() if run.completed_at else None,
                    run.duration_ms,
                    run.source_count,
                    run.span_count,
                    run.entity_count,
                    run.relation_count,
                    run.error,
                ),
            )
            connection.execute(
                "DELETE FROM analysis_run_sources WHERE run_id = ?",
                (run.run_id,),
            )
            connection.executemany(
                """
                INSERT INTO analysis_run_sources (run_id, source_id, position)
                VALUES (?, ?, ?)
                """,
                [
                    (run.run_id, source_id, position)
                    for position, source_id in enumerate(run.source_ids)
                ],
            )
            connection.execute("DELETE FROM analysis_entities WHERE run_id = ?", (run.run_id,))

            for entity in analysis.entities:
                connection.execute(
                    """
                    INSERT INTO analysis_entities (
                        entity_id, run_id, canonical_name, entity_type,
                        normalized_key, mention_count
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entity.entity_id,
                        entity.run_id,
                        entity.canonical_name,
                        entity.entity_type,
                        entity.normalized_key,
                        entity.mention_count,
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO analysis_entity_mentions (
                        mention_id, entity_id, source_id, span_id, text,
                        start_char, end_char
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            mention.mention_id,
                            mention.entity_id,
                            mention.source_id,
                            mention.span_id,
                            mention.text,
                            mention.start_char,
                            mention.end_char,
                        )
                        for mention in entity.mentions
                    ],
                )

            for relation in analysis.relations:
                connection.execute(
                    """
                    INSERT INTO analysis_relations (
                        relation_id, run_id, subject_entity_id, predicate,
                        object_entity_id, polarity, polarity_method,
                        extraction_score, extraction_method
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        relation.relation_id,
                        relation.run_id,
                        relation.subject_entity_id,
                        relation.predicate,
                        relation.object_entity_id,
                        relation.polarity.value,
                        relation.polarity_method,
                        relation.extraction_score,
                        relation.extraction_method,
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO analysis_relation_evidence (
                        evidence_id, relation_id, source_id, span_id, text,
                        sentence_start, sentence_end
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            evidence.evidence_id,
                            evidence.relation_id,
                            evidence.source_id,
                            evidence.span_id,
                            evidence.text,
                            evidence.sentence_start,
                            evidence.sentence_end,
                        )
                        for evidence in relation.evidence
                    ],
                )
        return analysis

    def get(self, run_id: str) -> WorkspaceAnalysis | None:
        with self._connect() as connection:
            run_row = connection.execute(
                "SELECT * FROM analysis_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if run_row is None:
                return None
            entity_rows = connection.execute(
                """
                SELECT * FROM analysis_entities
                WHERE run_id = ?
                ORDER BY mention_count DESC, canonical_name COLLATE NOCASE ASC
                """,
                (run_id,),
            ).fetchall()
            relation_rows = connection.execute(
                """
                SELECT * FROM analysis_relations
                WHERE run_id = ?
                ORDER BY extraction_score DESC, predicate ASC
                """,
                (run_id,),
            ).fetchall()

            run = self._run_from_row(connection, run_row)
            entities = [self._entity_from_row(connection, row) for row in entity_rows]
            relations = [self._relation_from_row(connection, row) for row in relation_rows]

        return WorkspaceAnalysis(run=run, entities=entities, relations=relations)

    def latest_for_workspace(self, workspace_id: str) -> WorkspaceAnalysis | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT run_id FROM analysis_runs
                WHERE workspace_id = ? AND status = ?
                ORDER BY started_at DESC LIMIT 1
                """,
                (workspace_id, AnalysisStatus.COMPLETED.value),
            ).fetchone()
        return self.get(row["run_id"]) if row is not None else None

    def list_runs(self, workspace_id: str, limit: int = 20) -> list[AnalysisRun]:
        safe_limit = max(1, min(limit, 100))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM analysis_runs
                WHERE workspace_id = ?
                ORDER BY started_at DESC LIMIT ?
                """,
                (workspace_id, safe_limit),
            ).fetchall()
            return [self._run_from_row(connection, row) for row in rows]

    def clear(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM analysis_runs")

    @staticmethod
    def _run_from_row(
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> AnalysisRun:
        source_rows = connection.execute(
            """
            SELECT source_id FROM analysis_run_sources
            WHERE run_id = ? ORDER BY position ASC
            """,
            (row["run_id"],),
        ).fetchall()
        return AnalysisRun(
            run_id=row["run_id"],
            workspace_id=row["workspace_id"],
            status=AnalysisStatus(row["status"]),
            pipeline_version=row["pipeline_version"],
            model_name=row["model_name"],
            model_version=row["model_version"],
            extractor_version=row["extractor_version"],
            resolver_version=row["resolver_version"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            duration_ms=row["duration_ms"],
            source_count=row["source_count"],
            source_ids=[source_row["source_id"] for source_row in source_rows],
            span_count=row["span_count"],
            entity_count=row["entity_count"],
            relation_count=row["relation_count"],
            error=row["error"],
        )

    @staticmethod
    def _entity_from_row(connection: sqlite3.Connection, row: sqlite3.Row) -> Entity:
        mentions = connection.execute(
            """
            SELECT * FROM analysis_entity_mentions
            WHERE entity_id = ? ORDER BY source_id, span_id, start_char
            """,
            (row["entity_id"],),
        ).fetchall()
        return Entity(
            entity_id=row["entity_id"],
            run_id=row["run_id"],
            canonical_name=row["canonical_name"],
            entity_type=row["entity_type"],
            normalized_key=row["normalized_key"],
            mention_count=row["mention_count"],
            mentions=[
                EntityMention(
                    mention_id=mention["mention_id"],
                    entity_id=mention["entity_id"],
                    source_id=mention["source_id"],
                    span_id=mention["span_id"],
                    text=mention["text"],
                    start_char=mention["start_char"],
                    end_char=mention["end_char"],
                )
                for mention in mentions
            ],
        )

    @staticmethod
    def _relation_from_row(connection: sqlite3.Connection, row: sqlite3.Row) -> Relation:
        evidence_rows = connection.execute(
            """
            SELECT * FROM analysis_relation_evidence
            WHERE relation_id = ? ORDER BY source_id, span_id, sentence_start
            """,
            (row["relation_id"],),
        ).fetchall()
        return Relation(
            relation_id=row["relation_id"],
            run_id=row["run_id"],
            subject_entity_id=row["subject_entity_id"],
            predicate=row["predicate"],
            object_entity_id=row["object_entity_id"],
            polarity=AssertionPolarity(row["polarity"]),
            polarity_method=row["polarity_method"],
            extraction_score=row["extraction_score"],
            extraction_method=row["extraction_method"],
            evidence=[
                RelationEvidence(
                    evidence_id=evidence["evidence_id"],
                    relation_id=evidence["relation_id"],
                    source_id=evidence["source_id"],
                    span_id=evidence["span_id"],
                    text=evidence["text"],
                    sentence_start=evidence["sentence_start"],
                    sentence_end=evidence["sentence_end"],
                )
                for evidence in evidence_rows
            ],
        )


@lru_cache
def get_analysis_repository() -> AnalysisRepository:
    return SqliteAnalysisRepository(get_settings().database_path)
