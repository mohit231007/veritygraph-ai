from __future__ import annotations

import re
from hashlib import sha256
from urllib.parse import unquote, urlsplit

from app.domain.source import (
    BibliographicIdentifierKind,
    IdentifierObservationRole,
    SourceIdentifier,
    SourceReference,
    SourceSpan,
)

_ASCII_LOWER = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
)
_DOI_PATTERN = re.compile(
    r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+",
    re.IGNORECASE | re.ASCII,
)
_ARXIV_PREFIX_PATTERN = re.compile(
    r"\barxiv\s*:\s*"
    r"(?P<identifier>(?:\d{4}\.\d{4,5}|[A-Z][A-Z0-9.-]*/\d{7}))"
    r"(?:v(?P<version>[1-9]\d*))?\b",
    re.IGNORECASE | re.ASCII,
)
_ARXIV_ID_PATTERN = re.compile(
    r"^(?P<identifier>(?:\d{4}\.\d{4,5}|[A-Z][A-Z0-9.-]*/\d{7}))"
    r"(?:v(?P<version>[1-9]\d*))?$",
    re.IGNORECASE | re.ASCII,
)
_ISBN_PATTERN = re.compile(
    r"\bISBN(?:-1[03])?\s*:?\s*"
    r"(?P<identifier>[0-9X][0-9X\- ]{8,24}[0-9X])",
    re.IGNORECASE | re.ASCII,
)
_DOI_HOSTS = {"doi.org", "dx.doi.org", "www.doi.org"}
_ARXIV_HOSTS = {"arxiv.org", "www.arxiv.org"}
_DOI_TRAILING_PUNCTUATION = ".,;:!?]}"


def _ascii_lower(value: str) -> str:
    return value.translate(_ASCII_LOWER)


def _normalize_doi(value: str) -> str | None:
    candidate = value.strip().rstrip(_DOI_TRAILING_PUNCTUATION)
    while candidate.endswith(")") and candidate.count(")") > candidate.count("("):
        candidate = candidate[:-1]
    if not _DOI_PATTERN.fullmatch(candidate):
        return None
    return _ascii_lower(candidate)


def _isbn13_check_digit(first_twelve: str) -> str:
    total = sum(
        int(character) * (1 if index % 2 == 0 else 3)
        for index, character in enumerate(first_twelve)
    )
    return str((10 - (total % 10)) % 10)


def _valid_isbn13(value: str) -> bool:
    return len(value) == 13 and value.isdigit() and _isbn13_check_digit(value[:12]) == value[-1]


def _valid_isbn10(value: str) -> bool:
    if len(value) != 10 or not value[:9].isdigit():
        return False
    check = 10 if value[-1] == "X" else int(value[-1]) if value[-1].isdigit() else -1
    if check < 0:
        return False
    total = sum((10 - index) * int(character) for index, character in enumerate(value[:9]))
    total += check
    return total % 11 == 0


def _normalize_isbn(value: str) -> str | None:
    compact = re.sub(r"[\s-]+", "", value).upper()
    if _valid_isbn13(compact):
        return compact
    if not _valid_isbn10(compact):
        return None
    first_twelve = f"978{compact[:9]}"
    return f"{first_twelve}{_isbn13_check_digit(first_twelve)}"


def _normalize_arxiv(value: str) -> tuple[str, int | None] | None:
    candidate = value.strip().removesuffix(".pdf")
    match = _ARXIV_ID_PATTERN.fullmatch(candidate)
    if match is None:
        return None
    base = _ascii_lower(match.group("identifier"))
    version = int(match.group("version")) if match.group("version") else None
    return base, version


def _identifier_id(
    *,
    source_id: str,
    kind: BibliographicIdentifierKind,
    normalized_value: str,
    role: IdentifierObservationRole,
    span_id: str | None,
    reference_id: str | None,
    version: int | None,
    extraction_method: str,
) -> str:
    material = "|".join(
        [
            source_id,
            kind.value,
            normalized_value,
            role.value,
            span_id or "",
            reference_id or "",
            str(version or ""),
            extraction_method,
        ]
    )
    return f"bid_{sha256(material.encode('utf-8')).hexdigest()[:24]}"


def _build_identifier(
    *,
    source_id: str,
    kind: BibliographicIdentifierKind,
    raw_value: str,
    normalized_value: str,
    role: IdentifierObservationRole,
    extraction_method: str,
    span_id: str | None = None,
    reference_id: str | None = None,
    page_number: int | None = None,
    paragraph_number: int | None = None,
    version: int | None = None,
    context_text: str | None = None,
) -> SourceIdentifier:
    return SourceIdentifier(
        identifier_id=_identifier_id(
            source_id=source_id,
            kind=kind,
            normalized_value=normalized_value,
            role=role,
            span_id=span_id,
            reference_id=reference_id,
            version=version,
            extraction_method=extraction_method,
        ),
        source_id=source_id,
        kind=kind,
        raw_value=raw_value,
        normalized_value=normalized_value,
        role=role,
        span_id=span_id,
        reference_id=reference_id,
        page_number=page_number,
        paragraph_number=paragraph_number,
        version=version,
        context_text=context_text,
        extraction_method=extraction_method,
    )


def _from_text(
    *,
    source_id: str,
    text: str,
    role: IdentifierObservationRole,
    extraction_method: str,
    span_id: str | None = None,
    reference_id: str | None = None,
    page_number: int | None = None,
    paragraph_number: int | None = None,
) -> list[SourceIdentifier]:
    identifiers: list[SourceIdentifier] = []

    for match in _DOI_PATTERN.finditer(text):
        raw = match.group(0)
        normalized = _normalize_doi(raw)
        if normalized is None:
            continue
        identifiers.append(
            _build_identifier(
                source_id=source_id,
                kind=BibliographicIdentifierKind.DOI,
                raw_value=raw,
                normalized_value=normalized,
                role=role,
                span_id=span_id,
                reference_id=reference_id,
                page_number=page_number,
                paragraph_number=paragraph_number,
                context_text=text,
                extraction_method=extraction_method,
            )
        )

    for match in _ARXIV_PREFIX_PATTERN.finditer(text):
        raw = match.group("identifier")
        if match.group("version"):
            raw = f"{raw}v{match.group('version')}"
        normalized = _normalize_arxiv(raw)
        if normalized is None:
            continue
        base, version = normalized
        identifiers.append(
            _build_identifier(
                source_id=source_id,
                kind=BibliographicIdentifierKind.ARXIV,
                raw_value=raw,
                normalized_value=base,
                role=role,
                span_id=span_id,
                reference_id=reference_id,
                page_number=page_number,
                paragraph_number=paragraph_number,
                version=version,
                context_text=text,
                extraction_method=extraction_method,
            )
        )

    for match in _ISBN_PATTERN.finditer(text):
        raw = match.group("identifier").strip()
        normalized = _normalize_isbn(raw)
        if normalized is None:
            continue
        identifiers.append(
            _build_identifier(
                source_id=source_id,
                kind=BibliographicIdentifierKind.ISBN,
                raw_value=raw,
                normalized_value=normalized,
                role=role,
                span_id=span_id,
                reference_id=reference_id,
                page_number=page_number,
                paragraph_number=paragraph_number,
                context_text=text,
                extraction_method=extraction_method,
            )
        )
    return identifiers


def _from_reference_url(
    *,
    source_id: str,
    reference: SourceReference,
) -> list[SourceIdentifier]:
    try:
        parsed = urlsplit(reference.target_url)
    except ValueError:
        return []
    host = (parsed.hostname or "").rstrip(".").lower()

    if host in _DOI_HOSTS:
        raw = unquote(parsed.path.lstrip("/"))
        normalized = _normalize_doi(raw)
        if normalized is None:
            return []
        return [
            _build_identifier(
                source_id=source_id,
                kind=BibliographicIdentifierKind.DOI,
                raw_value=raw,
                normalized_value=normalized,
                role=IdentifierObservationRole.REFERENCE,
                span_id=reference.span_id,
                reference_id=reference.reference_id,
                page_number=reference.page_number,
                paragraph_number=reference.paragraph_number,
                context_text=reference.reference_text or reference.context_text,
                extraction_method="reference_url_identifier_v1",
            )
        ]

    if host in _ARXIV_HOSTS:
        path = unquote(parsed.path).strip("/")
        for prefix in ("abs/", "pdf/"):
            if path.startswith(prefix):
                raw = path.removeprefix(prefix)
                normalized = _normalize_arxiv(raw)
                if normalized is None:
                    return []
                base, version = normalized
                return [
                    _build_identifier(
                        source_id=source_id,
                        kind=BibliographicIdentifierKind.ARXIV,
                        raw_value=raw,
                        normalized_value=base,
                        role=IdentifierObservationRole.REFERENCE,
                        span_id=reference.span_id,
                        reference_id=reference.reference_id,
                        page_number=reference.page_number,
                        paragraph_number=reference.paragraph_number,
                        version=version,
                        context_text=reference.reference_text or reference.context_text,
                        extraction_method="reference_url_identifier_v1",
                    )
                ]
    return []


def extract_source_identifiers(
    *,
    source_id: str,
    spans: list[SourceSpan],
    references: list[SourceReference],
) -> list[SourceIdentifier]:
    """Retain explicit DOI/arXiv/ISBN observations without assigning citation semantics."""

    observations: list[SourceIdentifier] = []
    for span in spans:
        observations.extend(
            _from_text(
                source_id=source_id,
                text=span.text,
                role=IdentifierObservationRole.MENTION,
                span_id=span.span_id,
                page_number=span.page_number,
                paragraph_number=span.paragraph_number,
                extraction_method="visible_bibliographic_identifier_v1",
            )
        )

    for reference in references:
        if reference.reference_text:
            observations.extend(
                _from_text(
                    source_id=source_id,
                    text=reference.reference_text,
                    role=IdentifierObservationRole.REFERENCE,
                    span_id=reference.span_id,
                    reference_id=reference.reference_id,
                    page_number=reference.page_number,
                    paragraph_number=reference.paragraph_number,
                    extraction_method="reference_text_identifier_v1",
                )
            )
        observations.extend(_from_reference_url(source_id=source_id, reference=reference))

    chosen: dict[
        tuple[
            BibliographicIdentifierKind,
            str,
            IdentifierObservationRole,
            str | None,
            str | None,
            int | None,
        ],
        SourceIdentifier,
    ] = {}
    priority = {
        "visible_bibliographic_identifier_v1": 1,
        "reference_text_identifier_v1": 2,
        "reference_url_identifier_v1": 3,
    }
    for observation in observations:
        key = (
            observation.kind,
            observation.normalized_value,
            observation.role,
            observation.span_id,
            observation.reference_id,
            observation.version,
        )
        existing = chosen.get(key)
        if existing is None or priority[observation.extraction_method] > priority[
            existing.extraction_method
        ]:
            chosen[key] = observation

    return sorted(
        chosen.values(),
        key=lambda item: (
            item.kind.value,
            item.normalized_value,
            item.role.value,
            item.version or 0,
            item.span_id or "",
            item.reference_id or "",
            item.identifier_id,
        ),
    )
