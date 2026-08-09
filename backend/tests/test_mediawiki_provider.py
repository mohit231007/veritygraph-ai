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


def test_mediawiki_tocdata_and_section_html_are_normalized() -> None:
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
        assert params.get("section") == "1"
        return httpx.Response(
            200,
            json={
                "parse": {
                    "pageid": PAGE_ID,
                    "text": (
                        "<div><p>Nvidia was founded in 1993.<sup class='reference'>[1]</sup></p>"
                        "<ul><li>It later expanded into accelerated computing.</li></ul>"
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
    assert fetched.sections[0].title == "History & growth"
    assert fetched.sections[0].paragraphs == [
        "Nvidia was founded in 1993.",
        "It later expanded into accelerated computing.",
        "Founder | Jensen Huang",
    ]
