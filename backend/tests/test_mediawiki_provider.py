import asyncio

import httpx
from app.ingestion.wikipedia import MediaWikiWikipediaProvider

PAGE_ID = 609498


def _provider(handler) -> MediaWikiWikipediaProvider:
    return MediaWikiWikipediaProvider(
        endpoint="https://en.wikipedia.org/w/api.php",
        language="en",
        timeout_seconds=2.0,
        user_agent="VerityGraph-test",
        transport=httpx.MockTransport(handler),
    )


def test_mediawiki_search_parses_official_search_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["action"] == "query"
        assert request.url.params["list"] == "search"
        assert request.url.params["formatversion"] == "2"
        return httpx.Response(
            200,
            json={
                "query": {
                    "search": [
                        {
                            "pageid": PAGE_ID,
                            "title": "Nvidia",
                            "snippet": (
                                "American <span class='searchmatch'>technology</span> "
                                "company"
                            ),
                            "wordcount": 6400,
                            "size": 190000,
                            "timestamp": "2026-08-01T12:30:00Z",
                        }
                    ]
                }
            },
        )

    results = asyncio.run(_provider(handler).search("NVIDIA", 5))

    assert len(results) == 1
    assert results[0].page_id == PAGE_ID
    assert results[0].snippet == "American technology company"
    assert results[0].updated_at is not None


def test_mediawiki_selected_section_preserves_only_its_citation_lineage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        if params.get("prop") == "tocdata|revid|displaytitle":
            return httpx.Response(
                200,
                json={
                    "parse": {
                        "title": "Nvidia",
                        "pageid": PAGE_ID,
                        "revid": 987654321,
                        "displaytitle": "<span>Nvidia</span>",
                        "tocdata": {
                            "sections": [
                                {
                                    "tocLevel": 1,
                                    "line": "History &amp; growth",
                                    "number": "1",
                                    "index": "1",
                                    "anchor": "History_&_growth",
                                },
                                {
                                    "tocLevel": 2,
                                    "line": "Early years",
                                    "number": "1.1",
                                    "index": "2",
                                    "anchor": "Early_years",
                                },
                                {
                                    "tocLevel": 1,
                                    "line": "Template heading",
                                    "number": "2",
                                    "index": "T-1",
                                },
                            ]
                        },
                    }
                },
            )

        assert params.get("prop") == "text"
        if params.get("section") is None:
            return httpx.Response(
                200,
                json={
                    "parse": {
                        "pageid": PAGE_ID,
                        "text": (
                            "<div><ol class='references'>"
                            "<li id='cite_note-source-1'>"
                            "<span class='mw-cite-backlink'>^</span>"
                            "<span class='reference-text'>Example Research. "
                            "<a class='external text' href='https://example.com/founding'>"
                            "Nvidia founding timeline</a>. Retrieved 2026.</span></li>"
                            "<li id='cite_note-unselected-2'>"
                            "<span class='reference-text'>Other Research. "
                            "<a class='external text' href='https://example.com/unselected'>"
                            "Unselected source</a>.</span></li>"
                            "</ol></div>"
                        ),
                    }
                },
            )

        assert params.get("section") == "1"
        return httpx.Response(
            200,
            json={
                "parse": {
                    "pageid": PAGE_ID,
                    "text": (
                        "<div><p>Nvidia was founded in 1993."
                        "<sup class='reference'><a href='#cite_note-source-1'>[1]</a></sup>"
                        "</p><ul><li>It later expanded into accelerated computing.</li></ul>"
                        "<table><tr><td>Founder</td><td>Jensen Huang</td></tr></table></div>"
                    ),
                }
            },
        )

    provider = _provider(handler)
    outline = asyncio.run(provider.outline(PAGE_ID))

    assert [section.index for section in outline.sections] == ["0", "1", "2"]
    assert outline.sections[1].title == "History & growth"
    assert outline.revision_id == 987654321

    fetched = asyncio.run(provider.fetch_sections(PAGE_ID, ["1"]))
    section = fetched.sections[0]
    assert section.title == "History & growth"
    assert section.paragraphs == [
        "Nvidia was founded in 1993.",
        "It later expanded into accelerated computing.",
        "Founder | Jensen Huang",
    ]
    assert len(section.references) == 1
    reference = section.references[0]
    assert reference.target_url == "https://example.com/founding"
    assert reference.anchor_text == "Nvidia founding timeline"
    assert reference.context_text == "Nvidia was founded in 1993."
    assert reference.reference_text == (
        "Example Research. Nvidia founding timeline. Retrieved 2026."
    )
    assert reference.citation_label == "[1]"
    assert reference.citation_marker == "cite_note-source-1"
    assert reference.extraction_method == "mediawiki_inline_citation_v1"
    assert all(
        item.target_url != "https://example.com/unselected"
        for item in section.references
    )


def test_selected_reference_list_section_preserves_direct_external_links() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        if params.get("prop") == "tocdata|revid|displaytitle":
            return httpx.Response(
                200,
                json={
                    "parse": {
                        "title": "Nvidia",
                        "pageid": PAGE_ID,
                        "revid": 123,
                        "displaytitle": "Nvidia",
                        "tocdata": {
                            "sections": [
                                {
                                    "tocLevel": 1,
                                    "line": "References",
                                    "number": "1",
                                    "index": "1",
                                    "anchor": "References",
                                }
                            ]
                        },
                    }
                },
            )
        if params.get("section") is None:
            return httpx.Response(200, json={"parse": {"pageid": PAGE_ID, "text": "<div/>"}})
        return httpx.Response(
            200,
            json={
                "parse": {
                    "pageid": PAGE_ID,
                    "text": (
                        "<ol class='references'><li id='cite_note-direct-1'>"
                        "<span class='reference-text'>Direct entry. "
                        "<a class='external text' href='https://example.org/direct'>"
                        "Primary report</a>.</span></li></ol>"
                    ),
                }
            },
        )

    fetched = asyncio.run(_provider(handler).fetch_sections(PAGE_ID, ["1"]))

    assert fetched.sections[0].paragraphs == ["Direct entry. Primary report ."]
    assert len(fetched.sections[0].references) == 1
    reference = fetched.sections[0].references[0]
    assert reference.target_url == "https://example.org/direct"
    assert reference.reference_text == "Direct entry. Primary report ."
    assert reference.citation_marker == "cite_note-direct-1"
    assert reference.extraction_method == "mediawiki_reference_list_v1"
