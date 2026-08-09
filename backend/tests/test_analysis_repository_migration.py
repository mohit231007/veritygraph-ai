import sqlite3

from app.repositories.analysis_repository import SqliteAnalysisRepository


def test_existing_analysis_database_adds_resolver_version_without_data_loss(tmp_path) -> None:
    database_path = tmp_path / "legacy-analysis.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE analysis_runs (
                run_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                status TEXT NOT NULL,
                pipeline_version TEXT NOT NULL,
                model_name TEXT NOT NULL,
                model_version TEXT NOT NULL,
                extractor_version TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                duration_ms INTEGER,
                source_count INTEGER NOT NULL,
                span_count INTEGER NOT NULL,
                entity_count INTEGER NOT NULL,
                relation_count INTEGER NOT NULL,
                error TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO analysis_runs (
                run_id, workspace_id, status, pipeline_version, model_name,
                model_version, extractor_version, started_at, completed_at,
                duration_ms, source_count, span_count, entity_count,
                relation_count, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run_legacy",
                "ws_legacy",
                "completed",
                "spacy-baseline-v1",
                "en_core_web_sm",
                "3.8.0",
                "dependency-relations-v1",
                "2026-08-09T00:00:00+00:00",
                "2026-08-09T00:00:01+00:00",
                1000,
                1,
                1,
                0,
                0,
                None,
            ),
        )

    repository = SqliteAnalysisRepository(database_path)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(analysis_runs)").fetchall()
        }
        resolver_version = connection.execute(
            "SELECT resolver_version FROM analysis_runs WHERE run_id = ?",
            ("run_legacy",),
        ).fetchone()[0]

    assert "resolver_version" in columns
    assert resolver_version == "none"
    restored = repository.get("run_legacy")
    assert restored is not None
    assert restored.run.resolver_version == "none"
