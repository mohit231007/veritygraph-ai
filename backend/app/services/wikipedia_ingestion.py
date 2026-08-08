from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from uuid import uuid4

from app.core.config import get_settings
from app.domain.source import SourceBundle, SourceDocument, SourceSpan, SourceType
from app.ingestion.wikipedia import (
    FixtureWikipediaProvider,
    MediaWikiWikipediaProvider,
    WikipediaProvider,
)
from app.repositories.source_repository import InMemorySourceRepository


def _new_span_id() -> str:
    return f"span_{uuid4().hex}"


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
    repository: InMemorySourceRepository,
) -> SourceBundle:
    """Fetch selected Wikipedia sections and normalize them into source spans."""

    fetched = await provider.fetch_sections(page_id, section_indices)
    source_id = f"src_{uuid4().hex}"

    spans: list[SourceSpan] = []
    cursor = 0
    normalized_parts: list[str] = []
    for section in fetched.sections:
        for paragraph_number, paragraph in enumerate(section.paragraphs, start=1):
            text = " ".join(paragraph.split()).strip()
            if not text:
                continue
            spans.append(
                SourceSpan(
                    span_id=_new_span_id(),
                    source_id=source_id,
                    text=text,
                    section=section.title,
                    paragraph_number=paragraph_number,
                    char_start=cursor,
                    char_end=cursor + len(text),
                )
            )
            normalized_parts.append(text)
            cursor += len(text) + 2

    if not spans:
        raise ValueError("Wikipedia import produced no readable evidence spans.")

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
        },
    )
    return repository.save(SourceBundle(document=document, spans=spans))
