import sqlite3

from app.repositories.analysis_repository import SqliteAnalysisRepository


def test_existing_analysis_database_adds_lineage_columns_without_data_loss(tmp_path) -> None:
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
            CREATE TABLE analysis_relations (
                relation_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                subject_entity_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_entity_id TEXT NOT NULL,
                extraction_score REAL NOT NULL,
                extraction_method TEXT NOT NULL
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
                1,
                None,
            ),
        )
        connection.execute(
            """
            INSERT INTO analysis_relations (
                relation_id, run_id, subject_entity_id, predicate,
                object_entity_id, extraction_score, extraction_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "rel_legacy",
                "run_legacy",
                "ent_subject",
                "acquire",
                "ent_object",
                0.92,
                "dependency_subject_object",
            ),
        )

    repository = SqliteAnalysisRepository(database_path)

    with sqlite3.connect(database_path) as connection:
        run_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(analysis_runs)").fetchall()
        }
        relation_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(analysis_relations)").fetchall()
        }
        resolver_version = connection.execute(
            "SELECT resolver_version FROM analysis_runs WHERE run_id = ?",
            ("run_legacy",),
        ).fetchone()[0]
        qualifier_row = connection.execute(
            """
            SELECT polarity, polarity_method, modality, modality_method,
                   temporal_years_json, temporal_method
            FROM analysis_relations WHERE relation_id = ?
            """,
            ("rel_legacy",),
        ).fetchone()

    assert "resolver_version" in run_columns
    assert resolver_version == "none"
    assert {
        "polarity",
        "polarity_method",
        "modality",
        "modality_method",
        "temporal_years_json",
        "temporal_method",
    }.issubset(relation_columns)
    assert qualifier_row == (
        "unknown",
        "historical_unknown",
        "unknown",
        "historical_unknown",
        "[]",
        "historical_unknown",
    )

    restored = repository.get("run_legacy")
    assert restored is not None
    assert restored.run.resolver_version == "none"
