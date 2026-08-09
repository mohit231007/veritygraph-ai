from datetime import UTC, datetime

from app.domain.lineage import ReferenceResolution
from app.domain.source import SourceBundle, SourceDocument, SourceSpan, SourceType
from app.domain.workspace import WorkspaceDetail
from app.repositories.source_repository import InMemorySourceRepository, SqliteSourceRepository
from app.services.reference_lineage import build_workspace_reference_lineage
from app.services.source_references import (
    extract_retained_html_anchor_references,
    extract_visible_url_references,
    normalize_reference_url,
)


def document(
    source_id: str,
    title: str,
    *,
    url: str | None = None,
    requested_url: str | None = None,
) -> SourceDocument:
    metadata: dict[str, str | int | float | bool | None] = {}
    if requested_url is not None:
        metadata["requested_url"] = requested_url
    return SourceDocument(
        source_id=source_id,
        source_type=SourceType.PUBLIC_URL if url else SourceType.DOCUMENT,
        title=title,
        filename=None if url else f"{title}.txt",
        url=url,
        source_format="html" if url else "txt",
        mime_type="text/html" if url else "text/plain",
        content_hash=source_id[-1] * 64,
        size_bytes=10,
        metadata=metadata,
    )


def span(source_id: str, text: str, index: int = 1) -> SourceSpan:
    return SourceSpan(
        span_id=f"span_{source_id}_{index}",
        source_id=source_id,
        text=text,
        paragraph_number=index,
        char_start=0,
        char_end=len(text),
    )


def workspace(*documents: SourceDocument) -> WorkspaceDetail:
    now = datetime.now(UTC)
    return WorkspaceDetail(
        workspace_id="ws_lineage",
        name="Lineage workspace",
        description="",
        created_at=now,
        updated_at=now,
        source_count=len(documents),
        sources=list(documents),
    )


def test_reference_url_normalization_is_exact_and_fragment_free() -> None:
    assert (
        normalize_reference_url("HTTPS://Example.COM:443/report?q=1#section")
        == "https://example.com/report?q=1"
    )
    assert normalize_reference_url("mailto:analyst@example.com") is None
    assert normalize_reference_url("javascript:alert(1)") is None


def test_visible_url_reference_is_tied_to_exact_span() -> None:
    source_id = "src_a"
    evidence = span(
        source_id,
        "See https://Example.com/report?id=7#methodology for the underlying report.",
    )

    references = extract_visible_url_references(source_id, [evidence])

    assert len(references) == 1
    reference = references[0]
    assert reference.span_id == evidence.span_id
    assert reference.target_url == "https://Example.com/report?id=7#methodology"
    assert reference.normalized_target_url == "https://example.com/report?id=7"
    assert reference.context_text == evidence.text
    assert reference.extraction_method == "visible_url_in_source_span_v1"


def test_html_anchor_is_retained_only_when_enclosing_text_is_evidence() -> None:
    source_id = "src_web"
    retained = span(source_id, "Mellanox technology connects accelerated systems.")
    html = b"""
    <html><body>
      <nav><a href="https://example.org/navigation">Navigation</a></nav>
      <article>
        <p>
          <a href="https://example.org/mellanox">Mellanox technology</a>
          connects accelerated systems.
        </p>
      </article>
    </body></html>
    """

    references = extract_retained_html_anchor_references(
        source_id=source_id,
        html=html,
        base_url="https://example.com/article",
        spans=[retained],
    )

    assert len(references) == 1
    assert references[0].span_id == retained.span_id
    assert references[0].normalized_target_url == "https://example.org/mellanox"
    assert references[0].anchor_text == "Mellanox technology"
    assert references[0].extraction_method == "html_anchor_in_retained_span_v1"


def test_lineage_resolves_unique_external_and_ambiguous_targets() -> None:
    repository = InMemorySourceRepository()
    citing = document("src_a", "memo")
    target_one = document(
        "src_b",
        "report-one",
        url="https://example.com/report",
        requested_url="https://www.example.com/report#top",
    )
    target_two = document("src_c", "report-copy", url="https://example.com/report")
    external_target = "https://external.example.org/research"
    citing_spans = [
        span(
            citing.source_id,
            f"Compare https://example.com/report and {external_target}.",
        )
    ]
    citing_refs = extract_visible_url_references(citing.source_id, citing_spans)
    repository.save(SourceBundle(document=citing, spans=citing_spans, references=citing_refs))
    repository.save(SourceBundle(document=target_one, spans=[]))

    unique = build_workspace_reference_lineage(
        workspace(citing, target_one),
        source_repository=repository,
    )
    unique_edge = next(
        edge
        for edge in unique.references
        if edge.normalized_target_url == "https://example.com/report"
    )
    assert unique_edge.resolution == ReferenceResolution.WORKSPACE_UNIQUE
    assert unique_edge.target_source_ids == [target_one.source_id]
    assert unique.summary.resolved_workspace_reference_count == 1
    assert unique.summary.external_reference_count == 1

    repository.save(SourceBundle(document=target_two, spans=[]))
    ambiguous = build_workspace_reference_lineage(
        workspace(citing, target_one, target_two),
        source_repository=repository,
    )
    ambiguous_edge = next(
        edge
        for edge in ambiguous.references
        if edge.normalized_target_url == "https://example.com/report"
    )
    assert ambiguous_edge.resolution == ReferenceResolution.WORKSPACE_AMBIGUOUS
    assert set(ambiguous_edge.target_source_ids) == {"src_b", "src_c"}
    assert ambiguous.summary.ambiguous_workspace_reference_count == 1


def test_sqlite_reference_provenance_survives_repository_recreation(tmp_path) -> None:
    database = tmp_path / "veritygraph.sqlite3"
    source_id = "src_persist"
    evidence = span(source_id, "Evidence: https://example.com/report.")
    refs = extract_visible_url_references(source_id, [evidence])
    bundle = SourceBundle(
        document=document(source_id, "persistent"),
        spans=[evidence],
        references=refs,
    )

    SqliteSourceRepository(database).save(bundle)
    restored = SqliteSourceRepository(database).get(source_id)

    assert restored is not None
    assert restored.references == refs
    assert restored.references[0].span_id == evidence.span_id
