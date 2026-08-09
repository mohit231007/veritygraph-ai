import asyncio
import sqlite3

from app.ingestion.wikipedia import FixtureWikipediaProvider
from app.repositories.source_repository import InMemorySourceRepository, SqliteSourceRepository
from app.services.wikipedia_ingestion import ingest_wikipedia_sections


def test_fixture_wikipedia_citation_is_separate_from_prose_and_span_linked() -> None:
    repository = InMemorySourceRepository()
    bundle = asyncio.run(
        ingest_wikipedia_sections(
            page_id=FixtureWikipediaProvider.PAGE_ID,
            section_indices=["1"],
            provider=FixtureWikipediaProvider(),
            repository=repository,
        )
    )

    assert [span.text for span in bundle.spans] == [
        "Nvidia was founded in 1993.",
        (
            "The company expanded from graphics into accelerated computing "
            "and data-center systems."
        ),
    ]
    assert len(bundle.references) == 1
    reference = bundle.references[0]
    assert reference.normalized_target_url == "https://example.com/research/nvidia-founding"
    assert reference.span_id == bundle.spans[0].span_id
    assert reference.paragraph_number == 1
    assert reference.context_text == "Nvidia was founded in 1993."
    assert reference.reference_text == (
        "Example Research. Nvidia founding timeline. Retrieved 2026."
    )
    assert reference.citation_label == "[1]"
    assert reference.citation_marker == "cite_note-fixture-history-1"
    assert reference.extraction_method == "mediawiki_inline_citation_v1"
    assert "example.com" not in bundle.spans[0].text
    assert bundle.document.metadata["reference_count"] == 1


def test_wikipedia_citation_survives_sqlite_repository_recreation(tmp_path) -> None:
    database = tmp_path / "veritygraph.sqlite3"
    first_repository = SqliteSourceRepository(database)
    bundle = asyncio.run(
        ingest_wikipedia_sections(
            page_id=FixtureWikipediaProvider.PAGE_ID,
            section_indices=["1"],
            provider=FixtureWikipediaProvider(),
            repository=first_repository,
        )
    )

    restored = SqliteSourceRepository(database).get(bundle.document.source_id)

    assert restored is not None
    assert restored.references == bundle.references
    assert restored.references[0].citation_label == "[1]"
    assert restored.references[0].citation_marker == "cite_note-fixture-history-1"
    assert restored.references[0].reference_text is not None


def test_sqlite_adds_wikipedia_reference_columns_without_historical_backfill(tmp_path) -> None:
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE source_references (
                reference_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                span_id TEXT,
                page_number INTEGER,
                paragraph_number INTEGER,
                target_url TEXT NOT NULL,
                normalized_target_url TEXT NOT NULL,
                anchor_text TEXT,
                context_text TEXT,
                extraction_method TEXT NOT NULL
            )
            """
        )

    SqliteSourceRepository(database)

    with sqlite3.connect(database) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(source_references)").fetchall()
        }
    assert "reference_text" in columns
    assert "citation_label" in columns
    assert "citation_marker" in columns
