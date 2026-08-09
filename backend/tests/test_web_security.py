import asyncio
import ipaddress

import httpx
import pytest
from app.ingestion.web import (
    SafeHttpWebFetcher,
    UnsafeUrlError,
    UnsupportedWebContentError,
    WebContentTooLargeError,
    validate_public_url,
)

PUBLIC_IP = ipaddress.ip_address("93.184.216.34")


async def public_resolver(_host: str, _port: int):
    return [PUBLIC_IP]


def run_validate(url: str) -> str:
    return asyncio.run(validate_public_url(url, public_resolver))


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file.txt",
        "https://user:password@example.com/secret",
        "https://example.com:8443/admin",
        "http://example.com:8080/admin",
        "http://127.0.0.1/admin",
        "http://10.0.0.1/internal",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/admin",
    ],
)
def test_public_url_validation_rejects_unsafe_targets(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        run_validate(url)


def test_public_url_validation_rejects_mixed_public_private_dns_answers() -> None:
    async def mixed_resolver(_host: str, _port: int):
        return [PUBLIC_IP, ipaddress.ip_address("10.0.0.10")]

    with pytest.raises(UnsafeUrlError, match="non-public network address"):
        asyncio.run(validate_public_url("https://example.com/article", mixed_resolver))


def test_public_url_validation_normalizes_fragment_and_hostname() -> None:
    safe = run_validate("https://EXAMPLE.com/research?q=graph#private-fragment")

    assert safe == "https://example.com/research?q=graph"


def _fetcher(handler, *, max_content_bytes: int = 1024, max_redirects: int = 2):
    return SafeHttpWebFetcher(
        timeout_seconds=2,
        max_content_bytes=max_content_bytes,
        max_redirects=max_redirects,
        user_agent="VerityGraph-test",
        resolver=public_resolver,
        transport=httpx.MockTransport(handler),
    )


def test_safe_fetcher_revalidates_redirect_target_before_following() -> None:
    request_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(302, headers={"location": "http://127.0.0.1/internal"})

    with pytest.raises(UnsafeUrlError):
        asyncio.run(_fetcher(handler).fetch("https://example.com/start"))

    assert request_count == 1


def test_safe_fetcher_rejects_unsupported_content_type() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"pdf")

    with pytest.raises(UnsupportedWebContentError):
        asyncio.run(_fetcher(handler).fetch("https://example.com/report"))


def test_safe_fetcher_rejects_declared_oversized_content() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "text/html",
                "content-length": "5000",
            },
            content=b"tiny test body",
        )

    with pytest.raises(WebContentTooLargeError):
        asyncio.run(
            _fetcher(handler, max_content_bytes=100).fetch("https://example.com/large")
        )


def test_safe_fetcher_rejects_streamed_content_that_exceeds_limit() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"x" * 101,
        )

    with pytest.raises(WebContentTooLargeError):
        asyncio.run(
            _fetcher(handler, max_content_bytes=100).fetch("https://example.com/large")
        )


def test_safe_fetcher_returns_bounded_public_html() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://example.com/article"
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=b"<html><body><p>Public research evidence.</p></body></html>",
        )

    page = asyncio.run(_fetcher(handler).fetch("https://example.com/article"))

    assert page.final_url == "https://example.com/article"
    assert page.mime_type == "text/html"
    assert page.redirect_count == 0
    assert b"Public research evidence" in page.content
