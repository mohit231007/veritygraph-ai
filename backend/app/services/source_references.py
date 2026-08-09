from __future__ import annotations

import re
from collections import defaultdict, deque
from hashlib import sha256
from io import BytesIO
from urllib.parse import urljoin, urlsplit, urlunsplit

import fitz
from bs4 import BeautifulSoup
from docx import Document
from docx.oxml.ns import qn

from app.domain.source import SourceReference, SourceSpan

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,;:!?)]}"
_REFERENCE_PRIORITY = {
    "visible_url_in_source_span_v1": 1,
    "html_anchor_in_retained_span_v1": 2,
    "docx_hyperlink_relationship_v1": 2,
    "pdf_link_annotation_v1": 2,
    "mediawiki_inline_citation_v1": 3,
    "mediawiki_reference_list_v1": 3,
}


def normalize_reference_url(url: str) -> str | None:
    """Return a conservative HTTP(S) URL identity for exact reference matching."""

    candidate = url.strip()
    if not candidate:
        return None
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError:
        return None

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        return None

    host = parsed.hostname.rstrip(".").lower()
    if not host:
        return None
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return None

    default_port = 443 if scheme == "https" else 80
    netloc = ascii_host if port in {None, default_port} else f"{ascii_host}:{port}"
    path = parsed.path or "/"
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def _normalized_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _reference_id(
    source_id: str,
    span_id: str | None,
    normalized_target_url: str,
    extraction_method: str,
) -> str:
    material = "|".join(
        [source_id, span_id or "unscoped", normalized_target_url, extraction_method]
    )
    return f"ref_{sha256(material.encode('utf-8')).hexdigest()[:24]}"


def build_source_reference(
    *,
    source_id: str,
    span_id: str | None,
    target_url: str,
    normalized_target_url: str,
    extraction_method: str,
    page_number: int | None = None,
    paragraph_number: int | None = None,
    anchor_text: str | None = None,
    context_text: str | None = None,
    reference_text: str | None = None,
) -> SourceReference:
    """Build one deterministic persisted source reference."""

    return SourceReference(
        reference_id=_reference_id(
            source_id,
            span_id,
            normalized_target_url,
            extraction_method,
        ),
        source_id=source_id,
        span_id=span_id,
        page_number=page_number,
        paragraph_number=paragraph_number,
        target_url=target_url,
        normalized_target_url=normalized_target_url,
        anchor_text=anchor_text,
        context_text=context_text,
        reference_text=reference_text,
        extraction_method=extraction_method,
    )


def extract_visible_url_references(
    source_id: str,
    spans: list[SourceSpan],
) -> list[SourceReference]:
    """Extract URLs that are literally visible inside retained evidence spans."""

    references: list[SourceReference] = []
    seen: set[tuple[str, str]] = set()
    for span in spans:
        for match in _URL_PATTERN.finditer(span.text):
            target_url = match.group(0).rstrip(_TRAILING_PUNCTUATION)
            normalized = normalize_reference_url(target_url)
            if normalized is None:
                continue
            key = (span.span_id, normalized)
            if key in seen:
                continue
            seen.add(key)
            references.append(
                build_source_reference(
                    source_id=source_id,
                    span_id=span.span_id,
                    page_number=span.page_number,
                    paragraph_number=span.paragraph_number,
                    target_url=target_url,
                    normalized_target_url=normalized,
                    extraction_method="visible_url_in_source_span_v1",
                    context_text=span.text,
                )
            )
    return references


def extract_retained_html_anchor_references(
    *,
    source_id: str,
    html: bytes,
    base_url: str,
    spans: list[SourceSpan],
) -> list[SourceReference]:
    """Retain HTML anchors only when their enclosing text survived as evidence."""

    soup = BeautifulSoup(html, "html.parser")
    spans_by_text: dict[str, SourceSpan] = {}
    for span in spans:
        normalized = _normalized_text(span.text)
        if normalized and normalized not in spans_by_text:
            spans_by_text[normalized] = span

    references: list[SourceReference] = []
    seen: set[tuple[str, str]] = set()
    for anchor in soup.find_all("a", href=True):
        parent = anchor.find_parent(["p", "li", "tr"])
        if parent is None:
            continue
        context_text = _normalized_text(parent.get_text(" ", strip=True))
        span = spans_by_text.get(context_text)
        if span is None:
            continue

        target_url = urljoin(base_url, str(anchor.get("href", "")).strip())
        normalized = normalize_reference_url(target_url)
        if normalized is None:
            continue
        key = (span.span_id, normalized)
        if key in seen:
            continue
        seen.add(key)
        anchor_text = _normalized_text(anchor.get_text(" ", strip=True)) or None
        references.append(
            build_source_reference(
                source_id=source_id,
                span_id=span.span_id,
                page_number=span.page_number,
                paragraph_number=span.paragraph_number,
                target_url=target_url,
                normalized_target_url=normalized,
                extraction_method="html_anchor_in_retained_span_v1",
                anchor_text=anchor_text,
                context_text=span.text,
            )
        )
    return references


def extract_docx_hyperlink_references(
    *,
    source_id: str,
    content: bytes,
    spans: list[SourceSpan],
) -> list[SourceReference]:
    """Extract external DOCX hyperlink relationships without rewriting visible text."""

    try:
        document = Document(BytesIO(content))
    except Exception:
        return []

    span_queues: dict[str, deque[SourceSpan]] = defaultdict(deque)
    for span in spans:
        if span.section is None:
            span_queues[_normalized_text(span.text)].append(span)

    references: list[SourceReference] = []
    for paragraph in document.paragraphs:
        context = _normalized_text(
            "".join(node.text or "" for node in paragraph._p.iter(qn("w:t")))
        )
        matching_span = span_queues[context].popleft() if span_queues[context] else None
        for hyperlink in paragraph._p.iter(qn("w:hyperlink")):
            relationship_id = hyperlink.get(qn("r:id"))
            if not relationship_id:
                continue
            try:
                relationship = paragraph.part.rels[relationship_id]
            except KeyError:
                continue
            target_url = str(relationship.target_ref).strip()
            normalized = normalize_reference_url(target_url)
            if normalized is None:
                continue
            anchor_text = _normalized_text(
                "".join(node.text or "" for node in hyperlink.iter(qn("w:t")))
            ) or None
            references.append(
                build_source_reference(
                    source_id=source_id,
                    span_id=matching_span.span_id if matching_span else None,
                    page_number=matching_span.page_number if matching_span else None,
                    paragraph_number=(
                        matching_span.paragraph_number if matching_span else None
                    ),
                    target_url=target_url,
                    normalized_target_url=normalized,
                    extraction_method="docx_hyperlink_relationship_v1",
                    anchor_text=anchor_text,
                    context_text=matching_span.text if matching_span else context or None,
                )
            )
    return references


def extract_pdf_link_annotation_references(
    *,
    source_id: str,
    content: bytes,
    spans: list[SourceSpan],
) -> list[SourceReference]:
    """Extract external PDF URI annotations with page provenance."""

    try:
        pdf = fitz.open(stream=content, filetype="pdf")
    except Exception:
        return []

    spans_by_page = {
        span.page_number: span for span in spans if span.page_number is not None
    }
    references: list[SourceReference] = []
    try:
        for page_index, page in enumerate(pdf, start=1):
            span = spans_by_page.get(page_index)
            for link in page.get_links():
                if link.get("kind") != fitz.LINK_URI:
                    continue
                target_url = str(link.get("uri") or "").strip()
                normalized = normalize_reference_url(target_url)
                if normalized is None:
                    continue

                anchor_text = None
                link_rect = link.get("from")
                if link_rect is not None:
                    try:
                        anchor_text = _normalized_text(page.get_textbox(link_rect)) or None
                    except Exception:
                        anchor_text = None
                references.append(
                    build_source_reference(
                        source_id=source_id,
                        span_id=span.span_id if span else None,
                        page_number=page_index,
                        paragraph_number=span.paragraph_number if span else None,
                        target_url=target_url,
                        normalized_target_url=normalized,
                        extraction_method="pdf_link_annotation_v1",
                        anchor_text=anchor_text,
                        context_text=span.text if span else None,
                    )
                )
    finally:
        pdf.close()
    return references


def merge_references(*groups: list[SourceReference]) -> list[SourceReference]:
    """Deduplicate one source's references, preferring richer format metadata."""

    chosen: dict[tuple[str | None, int | None, str], SourceReference] = {}
    for reference in (item for group in groups for item in group):
        key = (
            reference.span_id,
            reference.page_number,
            reference.normalized_target_url,
        )
        existing = chosen.get(key)
        if existing is None or _REFERENCE_PRIORITY.get(reference.extraction_method, 0) > (
            _REFERENCE_PRIORITY.get(existing.extraction_method, 0)
        ):
            chosen[key] = reference
    return sorted(
        chosen.values(),
        key=lambda item: (
            item.page_number or 0,
            item.paragraph_number or 0,
            item.span_id or "",
            item.normalized_target_url,
            item.extraction_method,
        ),
    )
