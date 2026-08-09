from __future__ import annotations

from abc import ABC, abstractmethod
from html import unescape

import httpx
from bs4 import BeautifulSoup

from app.domain.wikipedia import (
    WikipediaFetchedPage,
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


def _paragraphs_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select("script, style, noscript, sup.reference, .mw-editsection"):
        node.decompose()

    paragraphs: list[str] = []
    seen: set[str] = set()
    for node in soup.find_all(["p", "li", "tr"]):
        if node.name == "tr":
            cells = [
                _normalize_text(cell.get_text(" ", strip=True))
                for cell in node.find_all(["th", "td"])
            ]
            text = " | ".join(cell for cell in cells if cell)
        else:
            text = _normalize_text(node.get_text(" ", strip=True))
        if len(text) < 2 or text in seen:
            continue
        seen.add(text)
        paragraphs.append(text)
    return paragraphs


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
            parsed = payload.get("parse")
            if not parsed:
                raise WikipediaPageNotFoundError("Wikipedia page not found.")
            html = parsed.get("text", "")
            if isinstance(html, dict):
                html = html.get("*", "")
            paragraphs = _paragraphs_from_html(str(html))
            if paragraphs:
                fetched.append(
                    WikipediaFetchedSection(
                        index=index,
                        title=titles[index],
                        paragraphs=paragraphs,
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
