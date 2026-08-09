from __future__ import annotations

from abc import ABC, abstractmethod
from html import unescape
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from app.domain.wikipedia import (
    WikipediaFetchedPage,
    WikipediaFetchedReference,
    WikipediaFetchedSection,
    WikipediaOutline,
    WikipediaSearchResult,
    WikipediaSection,
)


class WikipediaProviderError(RuntimeError):
    """Raised when a Wikipedia provider cannot satisfy a request."""


class WikipediaPageNotFoundError(WikipediaProviderError):
    """Raised when the selected Wikipedia page no longer exists."""


class WikipediaProvider(ABC):
    @abstractmethod
    async def search(self, query: str, limit: int) -> list[WikipediaSearchResult]: ...

    @abstractmethod
    async def outline(self, page_id: int) -> WikipediaOutline: ...

    @abstractmethod
    async def fetch_sections(
        self,
        page_id: int,
        section_indices: list[str],
    ) -> WikipediaFetchedPage: ...


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _plain_text(html: str) -> str:
    soup = BeautifulSoup(unescape(html), "html.parser")
    return _normalize_text(soup.get_text(" ", strip=True))


def _node_text_without_reference_markers(node: Tag) -> str:
    clone = BeautifulSoup(str(node), "html.parser")
    for removable in clone.select("sup.reference, .mw-editsection"):
        removable.decompose()
    root = clone.find(node.name)
    if root is None:
        return ""
    if node.name == "tr":
        cells = [
            _normalize_text(cell.get_text(" ", strip=True))
            for cell in root.find_all(["th", "td"])
        ]
        return " | ".join(cell for cell in cells if cell)
    return _normalize_text(root.get_text(" ", strip=True))


def _paragraphs_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select("script, style, noscript, .mw-editsection"):
        node.decompose()

    paragraphs: list[str] = []
    seen: set[str] = set()
    for node in soup.find_all(["p", "li", "tr"]):
        text = _node_text_without_reference_markers(node)
        if len(text) < 2 or text in seen:
            continue
        seen.add(text)
        paragraphs.append(text)
    return paragraphs


def _external_http_target(href: str, page_url: str) -> str | None:
    candidate = unescape(href).strip()
    if not candidate or candidate.startswith("#"):
        return None
    if candidate.startswith("//"):
        candidate = f"https:{candidate}"
    elif not candidate.lower().startswith(("http://", "https://")):
        return None
    target = urljoin(page_url, candidate)
    if urlsplit(target).scheme.lower() not in {"http", "https"}:
        return None
    return target


def _reference_entry_text(node: Tag) -> str:
    clone = BeautifulSoup(str(node), "html.parser")
    for backlink in clone.select(".mw-cite-backlink"):
        backlink.decompose()
    root = clone.find(node.name)
    return _normalize_text(root.get_text(" ", strip=True)) if root else ""


def _reference_catalog(
    html: str,
    *,
    page_url: str,
) -> dict[str, list[WikipediaFetchedReference]]:
    """Catalog explicit external URLs from MediaWiki cite-note entries."""

    soup = BeautifulSoup(html, "html.parser")
    catalog: dict[str, list[WikipediaFetchedReference]] = {}
    for item in soup.find_all("li", id=lambda value: bool(value and value.startswith("cite_note-"))):
        marker = str(item.get("id"))
        reference_text = _reference_entry_text(item) or None
        entries: list[WikipediaFetchedReference] = []
        seen_targets: set[str] = set()
        for anchor in item.find_all("a", href=True):
            target = _external_http_target(str(anchor.get("href", "")), page_url)
            if target is None or target in seen_targets:
                continue
            seen_targets.add(target)
            entries.append(
                WikipediaFetchedReference(
                    target_url=target,
                    anchor_text=_normalize_text(anchor.get_text(" ", strip=True)) or None,
                    reference_text=reference_text,
                    citation_marker=marker,
                    extraction_method="mediawiki_reference_catalog_v1",
                )
            )
        if entries:
            catalog[marker] = entries
    return catalog


def _inline_citation_references(
    html: str,
    *,
    page_url: str,
    catalog: dict[str, list[WikipediaFetchedReference]],
) -> list[WikipediaFetchedReference]:
    """Resolve only cite-note markers that occur inside the selected section."""

    soup = BeautifulSoup(html, "html.parser")
    references: list[WikipediaFetchedReference] = []
    seen: set[tuple[str, str, str]] = set()

    for node in soup.find_all(["p", "li", "tr"]):
        context = _node_text_without_reference_markers(node)
        if not context:
            continue

        for superscript in node.select("sup.reference"):
            citation_label = _normalize_text(superscript.get_text(" ", strip=True)) or None
            for anchor in superscript.find_all("a", href=True):
                fragment = urlsplit(str(anchor.get("href", ""))).fragment
                if not fragment.startswith("cite_note-"):
                    continue
                for catalog_entry in catalog.get(fragment, []):
                    key = (context, fragment, catalog_entry.target_url)
                    if key in seen:
                        continue
                    seen.add(key)
                    references.append(
                        WikipediaFetchedReference(
                            target_url=catalog_entry.target_url,
                            anchor_text=catalog_entry.anchor_text,
                            context_text=context,
                            reference_text=catalog_entry.reference_text,
                            citation_label=citation_label,
                            citation_marker=fragment,
                            extraction_method="mediawiki_inline_citation_v1",
                        )
                    )

        if node.name != "li":
            continue
        marker_value = node.get("id")
        if not marker_value or not str(marker_value).startswith("cite_note-"):
            continue
        marker = str(marker_value)
        reference_text = _reference_entry_text(node) or None
        for anchor in node.find_all("a", href=True):
            target = _external_http_target(str(anchor.get("href", "")), page_url)
            if target is None:
                continue
            key = (context, marker, target)
            if key in seen:
                continue
            seen.add(key)
            references.append(
                WikipediaFetchedReference(
                    target_url=target,
                    anchor_text=_normalize_text(anchor.get_text(" ", strip=True)) or None,
                    context_text=context,
                    reference_text=reference_text,
                    citation_marker=marker,
                    extraction_method="mediawiki_reference_list_v1",
                )
            )
    return references


def _parse_text_html(payload: dict) -> str:
    parsed = payload.get("parse")
    if not parsed:
        raise WikipediaPageNotFoundError("Wikipedia page not found.")
    html = parsed.get("text", "")
    if isinstance(html, dict):
        html = html.get("*", "")
    return str(html)


class MediaWikiWikipediaProvider(WikipediaProvider):
    """Live Wikipedia adapter using the official MediaWiki Action API."""

    def __init__(
        self,
        *,
        endpoint: str,
        language: str,
        timeout_seconds: float,
        user_agent: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.language = language
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent
        self.transport = transport

    async def _get(self, params: dict[str, str | int]) -> dict:
        request_params: dict[str, str | int] = {
            "format": "json",
            "formatversion": 2,
            **params,
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                headers={"User-Agent": self.user_agent},
                transport=self.transport,
            ) as client:
                response = await client.get(self.endpoint, params=request_params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WikipediaProviderError(
                "Wikipedia could not be reached or returned invalid data."
            ) from exc

        if "error" in payload:
            code = payload["error"].get("code", "")
            if code in {"missingtitle", "nosuchpageid"}:
                raise WikipediaPageNotFoundError("Wikipedia page not found.")
            raise WikipediaProviderError(
                payload["error"].get("info", "Wikipedia request failed.")
            )
        return payload

    async def search(self, query: str, limit: int) -> list[WikipediaSearchResult]:
        payload = await self._get(
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "srprop": "size|wordcount|timestamp|snippet",
                "utf8": 1,
            }
        )
        items = payload.get("query", {}).get("search", [])
        return [
            WikipediaSearchResult(
                page_id=int(item["pageid"]),
                title=item["title"],
                snippet=_plain_text(item.get("snippet", "")),
                word_count=int(item.get("wordcount", 0)),
                size_bytes=int(item.get("size", 0)),
                updated_at=item.get("timestamp"),
            )
            for item in items
        ]

    async def outline(self, page_id: int) -> WikipediaOutline:
        payload = await self._get(
            {
                "action": "parse",
                "pageid": page_id,
                "prop": "tocdata|revid|displaytitle",
                "redirects": 1,
            }
        )
        parsed = payload.get("parse")
        if not parsed:
            raise WikipediaPageNotFoundError("Wikipedia page not found.")

        sections = [
            WikipediaSection(
                index="0",
                title="Overview",
                number="0",
                level=1,
                anchor="",
            )
        ]
        toc_sections = parsed.get("tocdata", {}).get("sections", [])
        for section in toc_sections:
            index = str(section.get("index", ""))
            if not index.isdigit():
                continue
            sections.append(
                WikipediaSection(
                    index=index,
                    title=_plain_text(section.get("line", "")) or f"Section {index}",
                    number=str(section.get("number", "")),
                    level=max(1, int(section.get("tocLevel", 1))),
                    anchor=section.get("anchor", ""),
                )
            )

        resolved_page_id = int(parsed.get("pageid", page_id))
        return WikipediaOutline(
            page_id=resolved_page_id,
            title=(
                _plain_text(parsed.get("displaytitle", ""))
                or parsed.get("title", "Wikipedia")
            ),
            revision_id=parsed.get("revid"),
            url=self._page_url(resolved_page_id),
            sections=sections,
        )

    async def fetch_sections(
        self,
        page_id: int,
        section_indices: list[str],
    ) -> WikipediaFetchedPage:
        outline = await self.outline(page_id)
        titles = {section.index: section.title for section in outline.sections}
        invalid = [index for index in section_indices if index not in titles]
        if invalid:
            raise WikipediaProviderError(
                f"Unknown Wikipedia section(s): {', '.join(invalid)}"
            )

        full_page_payload = await self._get(
            {
                "action": "parse",
                "pageid": page_id,
                "prop": "text",
                "redirects": 1,
            }
        )
        catalog = _reference_catalog(
            _parse_text_html(full_page_payload),
            page_url=outline.url,
        )

        fetched: list[WikipediaFetchedSection] = []
        for index in section_indices:
            payload = await self._get(
                {
                    "action": "parse",
                    "pageid": page_id,
                    "prop": "text",
                    "section": index,
                    "redirects": 1,
                }
            )
            html = _parse_text_html(payload)
            paragraphs = _paragraphs_from_html(html)
            if paragraphs:
                fetched.append(
                    WikipediaFetchedSection(
                        index=index,
                        title=titles[index],
                        paragraphs=paragraphs,
                        references=_inline_citation_references(
                            html,
                            page_url=outline.url,
                            catalog=catalog,
                        ),
                    )
                )

        if not fetched:
            raise WikipediaProviderError(
                "The selected Wikipedia sections contain no readable text."
            )

        return WikipediaFetchedPage(
            page_id=outline.page_id,
            title=outline.title,
            revision_id=outline.revision_id,
            url=outline.url,
            sections=fetched,
        )

    def _page_url(self, page_id: int) -> str:
        return f"https://{self.language}.wikipedia.org/?curid={page_id}"


class FixtureWikipediaProvider(WikipediaProvider):
    """Deterministic provider used only when explicitly selected for tests/E2E."""

    PAGE_ID = 609498

    async def search(self, query: str, limit: int) -> list[WikipediaSearchResult]:
        if not query.strip():
            return []
        result = WikipediaSearchResult(
            page_id=self.PAGE_ID,
            title="Nvidia",
            snippet=(
                "American technology company known for graphics processors "
                "and AI computing."
            ),
            word_count=6400,
            size_bytes=190000,
        )
        return [result][:limit]

    async def outline(self, page_id: int) -> WikipediaOutline:
        if page_id != self.PAGE_ID:
            raise WikipediaPageNotFoundError("Wikipedia page not found.")
        return WikipediaOutline(
            page_id=self.PAGE_ID,
            title="Nvidia",
            revision_id=123456789,
            url=f"https://en.wikipedia.org/?curid={self.PAGE_ID}",
            sections=[
                WikipediaSection(index="0", title="Overview", number="0", level=1),
                WikipediaSection(index="1", title="History", number="1", level=1),
                WikipediaSection(index="2", title="Products", number="2", level=1),
            ],
        )

    async def fetch_sections(
        self,
        page_id: int,
        section_indices: list[str],
    ) -> WikipediaFetchedPage:
        outline = await self.outline(page_id)
        content = {
            "0": [
                (
                    "Nvidia Corporation is an American technology company focused "
                    "on accelerated computing."
                ),
                (
                    "Its products include graphics processors and computing platforms "
                    "used in artificial intelligence."
                ),
            ],
            "1": [
                "Nvidia was founded in 1993.",
                (
                    "The company expanded from graphics into accelerated computing "
                    "and data-center systems."
                ),
            ],
            "2": [
                (
                    "Nvidia develops GeForce graphics products and data-center "
                    "computing platforms."
                )
            ],
        }
        references = {
            "0": [],
            "1": [
                WikipediaFetchedReference(
                    target_url="https://example.com/research/nvidia-founding",
                    anchor_text="Nvidia founding timeline",
                    context_text="Nvidia was founded in 1993.",
                    reference_text=(
                        "Example Research. Nvidia founding timeline. Retrieved 2026."
                    ),
                    citation_label="[1]",
                    citation_marker="cite_note-fixture-history-1",
                    extraction_method="mediawiki_inline_citation_v1",
                )
            ],
            "2": [],
        }
        titles = {section.index: section.title for section in outline.sections}
        unknown = [index for index in section_indices if index not in content]
        if unknown:
            raise WikipediaProviderError(
                f"Unknown Wikipedia section(s): {', '.join(unknown)}"
            )
        sections = [
            WikipediaFetchedSection(
                index=index,
                title=titles[index],
                paragraphs=content[index],
                references=references[index],
            )
            for index in section_indices
        ]
        return WikipediaFetchedPage(
            page_id=outline.page_id,
            title=outline.title,
            revision_id=outline.revision_id,
            url=outline.url,
            sections=sections,
        )
