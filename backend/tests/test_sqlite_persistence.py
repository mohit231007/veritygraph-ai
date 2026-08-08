from pathlib import Path

from app.domain.source import SourceBundle, SourceDocument, SourceSpan, SourceType
from app.domain.workspace import WorkspaceCreate
from app.repositories.source_repository import SqliteSourceRepository
from app.repositories.workspace_repository import SqliteWorkspaceRepository


def sample_bundle() -> SourceBundle:
    document = SourceDocument(
        source_id="src_persisted",
        source_type=SourceType.DOCUMENT,
        title="Persistence evidence",
        filename="evidence.txt",
        source_format="txt",
        mime_type="text/plain",
        content_hash="a" * 64,
        size_bytes=24,
        metadata={"span_count": 1},
    )
    span = SourceSpan(
        span_id="span_persisted",
        source_id=document.source_id,
        text="Persistent evidence survives repository recreation.",
        page_number=1,
        paragraph_number=1,
        char_start=0,
        char_end=48,
    )
    return SourceBundle(document=document, spans=[span])


def test_sqlite_source_survives_repository_recreation(tmp_path: Path) -> None:
    database = tmp_path / "veritygraph.db"
    first_repository = SqliteSourceRepository(database)
    bundle = sample_bundle()
    first_repository.save(bundle)

    second_repository = SqliteSourceRepository(database)
    restored = second_repository.get(bundle.document.source_id)

    assert restored == bundle
    assert second_repository.list_documents() == [bundle.document]


def test_workspace_membership_survives_repository_recreation(tmp_path: Path) -> None:
    database = tmp_path / "veritygraph.db"
    source_repository = SqliteSourceRepository(database)
    bundle = sample_bundle()
    source_repository.save(bundle)

    first_workspaces = SqliteWorkspaceRepository(database, source_repository)
    workspace = first_workspaces.create(
        WorkspaceCreate(name="NVIDIA research", description="Multi-source research workspace")
    )
    updated = first_workspaces.add_source(workspace.workspace_id, bundle.document.source_id)
    assert updated.source_count == 1

    second_sources = SqliteSourceRepository(database)
    second_workspaces = SqliteWorkspaceRepository(database, second_sources)
    restored = second_workspaces.get(workspace.workspace_id)

    assert restored is not None
    assert restored.source_count == 1
    assert restored.sources == [bundle.document]


def test_source_deletion_cascades_workspace_membership(tmp_path: Path) -> None:
    database = tmp_path / "veritygraph.db"
    source_repository = SqliteSourceRepository(database)
    bundle = sample_bundle()
    source_repository.save(bundle)
    workspaces = SqliteWorkspaceRepository(database, source_repository)
    workspace = workspaces.create(WorkspaceCreate(name="Cascade test"))
    workspaces.add_source(workspace.workspace_id, bundle.document.source_id)

    source_repository.clear()
    restored = workspaces.get(workspace.workspace_id)

    assert restored is not None
    assert restored.source_count == 0
    assert restored.sources == []
