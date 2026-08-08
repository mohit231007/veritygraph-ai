from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from typing import Protocol
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from app.domain.web import RawWebPage

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver = Callable[[str, int], Awaitable[list[IPAddress]]]


class WebFetcher(Protocol):
    async def fetch(self, url: str) -> RawWebPage: ...


class WebFetchError(RuntimeError):
    """Base error for public web retrieval failures."""


class UnsafeUrlError(WebFetchError):
    """Raised when a user-supplied URL could access a non-public target."""


class UnsupportedWebContentError(WebFetchError):
    """Raised when a response is not a supported text document."""


class WebContentTooLargeError(WebFetchError):
    """Raised when response content exceeds the configured safety limit."""


async def resolve_host(host: str, port: int) -> list[IPAddress]:
    """Resolve a hostname without blocking the event loop."""

    def lookup() -> list[tuple]:
        return socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)

    try:
        records = await asyncio.to_thread(lookup)
    except socket.gaierror as exc:
        raise WebFetchError("The public host could not be resolved.") from exc

    addresses: list[IPAddress] = []
    for record in records:
        raw_address = record[4][0]
        parsed = ipaddress.ip_address(raw_address)
        if parsed not in addresses:
            addresses.append(parsed)
    if not addresses:
        raise WebFetchError("The public host did not resolve to an IP address.")
    return addresses


def _is_public_address(address: IPAddress) -> bool:
    return (
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
    )


async def validate_public_url(url: str, resolver: Resolver = resolve_host) -> str:
    """Validate one HTTP(S) target before a server-side request is attempted.

    Every DNS answer must be globally routable. Rejecting mixed public/private answer
    sets avoids selecting a private target from a hostname that also has a public IP.
    """

    normalized = url.strip()
    if any(ord(character) < 32 for character in normalized):
        raise UnsafeUrlError("URL must not contain control characters.")

    try:
        parsed = urlsplit(normalized)
        port = parsed.port
    except ValueError as exc:
        raise UnsafeUrlError("URL contains an invalid port.") from exc

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise UnsafeUrlError("Only public HTTP and HTTPS URLs are allowed.")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeUrlError("URLs containing embedded credentials are not allowed.")

    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL must include a hostname.")
    host = host.rstrip(".").lower()
    if not host:
        raise UnsafeUrlError("URL must include a hostname.")

    expected_port = 443 if scheme == "https" else 80
    effective_port = port or expected_port
    if effective_port != expected_port:
        raise UnsafeUrlError(
            f"Only the standard {scheme.upper()} port {expected_port} is allowed."
        )

    try:
        literal_address = ipaddress.ip_address(host)
    except ValueError:
        try:
            ascii_host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise UnsafeUrlError("URL hostname is invalid.") from exc
        addresses = await resolver(ascii_host, effective_port)
    else:
        ascii_host = host
        addresses = [literal_address]

    if not addresses or any(not _is_public_address(address) for address in addresses):
        raise UnsafeUrlError(
            "URL resolves to a private, loopback, link-local, reserved, or otherwise "
            "non-public network address."
        )

    netloc = ascii_host
    if ":" in ascii_host and not ascii_host.startswith("["):
        netloc = f"[{ascii_host}]"
    path = parsed.path or "/"
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


class SafeHttpWebFetcher:
    """Bounded HTTP fetcher with SSRF-oriented target and redirect validation."""

    REDIRECT_STATUSES = {301, 302, 303, 307, 308}
    ALLOWED_MIME_TYPES = {
        "text/html",
        "application/xhtml+xml",
        "text/plain",
    }

    def __init__(
        self,
        *,
        timeout_seconds: float,
        max_content_bytes: int,
        max_redirects: int,
        user_agent: str,
        resolver: Resolver = resolve_host,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_content_bytes = max_content_bytes
        self.max_redirects = max_redirects
        self.user_agent = user_agent
        self.resolver = resolver
        self.transport = transport

    async def fetch(self, url: str) -> RawWebPage:
        requested_url = url.strip()
        current_url = requested_url

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds),
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8",
            },
            follow_redirects=False,
            transport=self.transport,
        ) as client:
            for redirect_count in range(self.max_redirects + 1):
                safe_url = await validate_public_url(current_url, self.resolver)
                try:
                    async with client.stream("GET", safe_url) as response:
                        if response.status_code in self.REDIRECT_STATUSES:
                            location = response.headers.get("location")
                            if not location:
                                raise WebFetchError(
                                    "Remote server returned a redirect without a location."
                                )
                            if redirect_count >= self.max_redirects:
                                raise WebFetchError("Remote server exceeded the redirect limit.")
                            current_url = urljoin(safe_url, location)
                            continue

                        try:
                            response.raise_for_status()
                        except httpx.HTTPStatusError as exc:
                            raise WebFetchError(
                                f"Remote server returned HTTP {response.status_code}."
                            ) from exc

                        mime_type = response.headers.get("content-type", "").split(";", 1)[0]
                        mime_type = mime_type.strip().lower()
                        if mime_type not in self.ALLOWED_MIME_TYPES:
                            raise UnsupportedWebContentError(
                                "Only HTML, XHTML, and plain-text public pages are supported."
                            )

                        content_length = response.headers.get("content-length")
                        if content_length:
                            try:
                                declared_size = int(content_length)
                            except ValueError:
                                declared_size = 0
                            if declared_size > self.max_content_bytes:
                                raise WebContentTooLargeError(
                                    "Public page exceeds the configured download size limit."
                                )

                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > self.max_content_bytes:
                                raise WebContentTooLargeError(
                                    "Public page exceeds the configured download size limit."
                                )

                        if not body:
                            raise WebFetchError("Public page returned an empty response body.")

                        return RawWebPage(
                            requested_url=requested_url,
                            final_url=safe_url,
                            mime_type=mime_type,
                            content=bytes(body),
                            redirect_count=redirect_count,
                            status_code=response.status_code,
                        )
                except httpx.RequestError as exc:
                    raise WebFetchError("Public page could not be reached.") from exc

        raise WebFetchError("Public page could not be retrieved.")


class FixtureWebFetcher:
    """Deterministic external-boundary replacement used only by E2E tests."""

    async def fetch(self, url: str) -> RawWebPage:
        requested_url = url.strip()
        html = b"""<!doctype html>
<html>
  <head><title>NVIDIA Networking Research</title></head>
  <body>
    <nav>Navigation that should not become primary evidence.</nav>
    <main>
      <article>
        <h1>NVIDIA Networking Research</h1>
        <p>NVIDIA acquired Mellanox Technologies to expand its networking portfolio.</p>
        <p>Mellanox technology connects accelerated computing systems in data centers.</p>
      </article>
    </main>
    <footer>Footer noise.</footer>
  </body>
</html>"""
        return RawWebPage(
            requested_url=requested_url,
            final_url="https://example.com/research/nvidia-networking",
            mime_type="text/html",
            content=html,
            redirect_count=0,
            status_code=200,
        )
