from __future__ import annotations

import re
from functools import lru_cache
from hashlib import sha256
from urllib.parse import urlsplit
from uuid import uuid4

from bs4 import BeautifulSoup
from trafilatura import extract

from app.core.config import get_settings
from app.domain.source import SourceBundle, SourceDocument, SourceSpan, SourceType
from app.domain.web import RawWebPage
from app.ingestion.web import FixtureWebFetcher, SafeHttpWebFetcher
from app.repositories.source_repository import InMemorySourceRepository


class WebExtractionError(ValueError):
    """Raised when a safe public page contains no usable main text."""


def _span_id() -> str:
    return f"span_{uuid4().hex}"


def _decode_text(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1252", errors="replace")


def _html_title(content: bytes, final_url: str) -> str:
    soup = BeautifulSoup(content, "html.parser")
    if soup.title:
        title = " ".join(soup.title.get_text(" ", strip=True).split())
        if title:
            return title
    return urlsplit(final_url).hostname or "Public web source"


def _extract_paragraphs(page: RawWebPage) -> tuple[str, list[str]]:
    if page.mime_type == "text/plain":
        text = _decode_text(page.content)
        title = urlsplit(page.final_url).hostname or "Public text source"
    else:
        title = _html_title(page.content, page.final_url)
        extracted = extract(
            page.content,
            url=page.final_url,
            output_format="txt",
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )
        if not extracted:
            raise WebExtractionError(
                "The public page did not contain enough readable main content to analyse."
            )
        text = extracted

    candidates = [" ".join(part.split()).strip() for part in re.split(r"\n+", text)]
    paragraphs: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if len(candidate) < 2 or candidate in seen:
            continue
        seen.add(candidate)
        paragraphs.append(candidate)

    if not paragraphs:
        raise WebExtractionError(
            "The public page did not contain enough readable main content to analyse."
        )
    return title, paragraphs


@lru_cache
def get_web_fetcher() -> SafeHttpWebFetcher | FixtureWebFetcher:
    settings = get_settings()
    provider = settings.web_provider.lower()
    if provider == "fixture":
        return FixtureWebFetcher()
    if provider != "live":
        raise RuntimeError("VERITYGRAPH_WEB_PROVIDER must be either 'live' or 'fixture'.")
    return SafeHttpWebFetcher(
        timeout_seconds=settings.web_timeout_seconds,
        max_content_bytes=settings.web_max_content_bytes,
        max_redirects=settings.web_max_redirects,
        user_agent=settings.web_user_agent,
    )


async def ingest_public_url(
    *,
    url: str,
    fetcher: SafeHttpWebFetcher | FixtureWebFetcher,
    repository: InMemorySourceRepository,
) -> SourceBundle:
    """Fetch a validated public page and convert main content into evidence spans."""

    page = await fetcher.fetch(url)
    title, paragraphs = _extract_paragraphs(page)
    source_id = f"src_{uuid4().hex}"

    spans: list[SourceSpan] = []
    cursor = 0
    for paragraph_number, paragraph in enumerate(paragraphs, start=1):
        spans.append(
            SourceSpan(
                span_id=_span_id(),
                source_id=source_id,
                text=paragraph,
                section="Main content",
                paragraph_number=paragraph_number,
                char_start=cursor,
                char_end=cursor + len(paragraph),
            )
        )
        cursor += len(paragraph) + 2

    normalized = "\n\n".join(paragraphs)
    host = urlsplit(page.final_url).hostname or ""
    source_format = "text" if page.mime_type == "text/plain" else "html"
    document = SourceDocument(
        source_id=source_id,
        source_type=SourceType.PUBLIC_URL,
        title=title,
        url=page.final_url,
        source_format=source_format,
        mime_type=page.mime_type,
        content_hash=sha256(normalized.encode("utf-8")).hexdigest(),
        size_bytes=len(page.content),
        metadata={
            "requested_url": page.requested_url,
            "final_url": page.final_url,
            "hostname": host,
            "redirect_count": page.redirect_count,
            "http_status": page.status_code,
            "fetched_bytes": len(page.content),
            "span_count": len(spans),
        },
    )
    return repository.save(SourceBundle(document=document, spans=spans))
