from __future__ import annotations

import re
from hashlib import sha256
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.domain.source import SourceReference, SourceSpan

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,;:!?)]}"


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


def _build_reference(
    *,
    source_id: str,
    span_id: str | None,
    target_url: str,
    normalized_target_url: str,
    extraction_method: str,
    anchor_text: str | None = None,
    context_text: str | None = None,
) -> SourceReference:
    return SourceReference(
        reference_id=_reference_id(
            source_id,
            span_id,
            normalized_target_url,
            extraction_method,
        ),
        source_id=source_id,
        span_id=span_id,
        target_url=target_url,
        normalized_target_url=normalized_target_url,
        anchor_text=anchor_text,
        context_text=context_text,
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
                _build_reference(
                    source_id=source_id,
                    span_id=span.span_id,
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
    """Retain HTML anchors only when their enclosing text survived as evidence.

    This deliberately rejects navigation/footer links that cannot be mapped to a
    retained paragraph/list/table-row span.
    """

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
            _build_reference(
                source_id=source_id,
                span_id=span.span_id,
                target_url=target_url,
                normalized_target_url=normalized,
                extraction_method="html_anchor_in_retained_span_v1",
                anchor_text=anchor_text,
                context_text=span.text,
            )
        )
    return references


def merge_references(*groups: list[SourceReference]) -> list[SourceReference]:
    """Deduplicate one source's references while preferring explicit HTML anchors."""

    chosen: dict[tuple[str | None, str], SourceReference] = {}
    for reference in (item for group in groups for item in group):
        key = (reference.span_id, reference.normalized_target_url)
        existing = chosen.get(key)
        if existing is None or reference.extraction_method.startswith("html_anchor"):
            chosen[key] = reference
    return sorted(
        chosen.values(),
        key=lambda item: (
            item.span_id or "",
            item.normalized_target_url,
            item.extraction_method,
        ),
    )
