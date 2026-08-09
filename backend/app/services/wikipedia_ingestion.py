from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from uuid import uuid4

from app.core.config import get_settings
from app.domain.source import (
    SourceBundle,
    SourceDocument,
    SourceReference,
    SourceSpan,
    SourceType,
)
from app.domain.wikipedia import WikipediaFetchedReference
from app.ingestion.wikipedia import (
    FixtureWikipediaProvider,
    MediaWikiWikipediaProvider,
    WikipediaProvider,
)
from app.repositories.source_repository import SourceRepository
from app.services.source_identifiers import extract_source_identifiers
from app.services.source_references import (
    build_source_reference,
    extract_visible_url_references,
    merge_references,
    normalize_reference_url,
)


def _new_span_id() -> str:
    return f"span_{uuid4().hex}"


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _reference_for_section(
    *,
    source_id: str,
    reference: WikipediaFetchedReference,
    section_spans: list[SourceSpan],
) -> SourceReference | None:
    normalized_target = normalize_reference_url(reference.target_url)
    if normalized_target is None:
        return None

    context = _normalize_text(reference.context_text or "")
    candidates = [span for span in section_spans if context and span.text == context]
    span = candidates[0] if len(candidates) == 1 else None
    return build_source_reference(
        source_id=source_id,
        span_id=span.span_id if span else None,
        page_number=span.page_number if span else None,
        paragraph_number=span.paragraph_number if span else None,
        target_url=reference.target_url,
        normalized_target_url=normalized_target,
        extraction_method=reference.extraction_method,
        anchor_text=reference.anchor_text,
        context_text=span.text if span else context or None,
        reference_text=reference.reference_text,
        citation_label=reference.citation_label,
        citation_marker=reference.citation_marker,
    )


@lru_cache
def get_wikipedia_provider() -> WikipediaProvider:
    settings = get_settings()
    if settings.wikipedia_provider.lower() == "fixture":
        return FixtureWikipediaProvider()
    if settings.wikipedia_provider.lower() != "live":
        raise RuntimeError(
            "VERITYGRAPH_WIKIPEDIA_PROVIDER must be either 'live' or 'fixture'."
        )
    return MediaWikiWikipediaProvider(
        endpoint=settings.wikipedia_endpoint,
        language=settings.wikipedia_language,
        timeout_seconds=settings.wikipedia_timeout_seconds,
        user_agent=settings.wikipedia_user_agent,
    )


async def ingest_wikipedia_sections(
    *,
    page_id: int,
    section_indices: list[str],
    provider: WikipediaProvider,
    repository: SourceRepository,
) -> SourceBundle:
    """Fetch selected Wikipedia sections and normalize them into source spans."""

    fetched = await provider.fetch_sections(page_id, section_indices)
    source_id = f"src_{uuid4().hex}"

    spans: list[SourceSpan] = []
    wikipedia_references: list[SourceReference] = []
    cursor = 0
    normalized_parts: list[str] = []
    for section in fetched.sections:
        section_spans: list[SourceSpan] = []
        for paragraph_number, paragraph in enumerate(section.paragraphs, start=1):
            text = _normalize_text(paragraph)
            if not text:
                continue
            span = SourceSpan(
                span_id=_new_span_id(),
                source_id=source_id,
                text=text,
                section=section.title,
                paragraph_number=paragraph_number,
                char_start=cursor,
                char_end=cursor + len(text),
            )
            spans.append(span)
            section_spans.append(span)
            normalized_parts.append(text)
            cursor += len(text) + 2

        for fetched_reference in section.references:
            reference = _reference_for_section(
                source_id=source_id,
                reference=fetched_reference,
                section_spans=section_spans,
            )
            if reference is not None:
                wikipedia_references.append(reference)

    if not spans:
        raise ValueError("Wikipedia import produced no readable evidence spans.")

    visible_references = extract_visible_url_references(source_id, spans)
    references = merge_references(visible_references, wikipedia_references)
    identifiers = extract_source_identifiers(
        source_id=source_id,
        spans=spans,
        references=references,
    )
    normalized = "\n\n".join(normalized_parts)
    document = SourceDocument(
        source_id=source_id,
        source_type=SourceType.WIKIPEDIA,
        title=fetched.title,
        url=fetched.url,
        source_format="wikipedia",
        mime_type="text/html",
        content_hash=sha256(normalized.encode("utf-8")).hexdigest(),
        size_bytes=len(normalized.encode("utf-8")),
        metadata={
            "page_id": fetched.page_id,
            "revision_id": fetched.revision_id,
            "selected_section_count": len(fetched.sections),
            "span_count": len(spans),
            "reference_count": len(references),
            "identifier_count": len(identifiers),
        },
    )
    return repository.save(
        SourceBundle(
            document=document,
            spans=spans,
            references=references,
            identifiers=identifiers,
        )
    )
