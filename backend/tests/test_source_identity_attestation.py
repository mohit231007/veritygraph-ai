import asyncio

from app.domain.source import IdentifierObservationRole
from app.domain.web import RawWebPage
from app.repositories.source_repository import InMemorySourceRepository
from app.services.web_ingestion import ingest_public_url


class RedirectedDoiFetcher:
    async def fetch(self, url: str) -> RawWebPage:
        return RawWebPage(
            requested_url=url,
            final_url="https://publisher.example/article/verity",
            mime_type="text/html",
            content=(
                b"<html><head><title>Verity paper</title></head>"
                b"<body><main><p>This paper discusses evidence provenance.</p>"
                b"</main></body></html>"
            ),
            redirect_count=1,
            status_code=200,
        )


class PublisherPathFetcher:
    async def fetch(self, url: str) -> RawWebPage:
        return RawWebPage(
            requested_url=url,
            final_url=url,
            mime_type="text/html",
            content=(
                b"<html><head><title>Publisher page</title></head>"
                b"<body><main><p>This page has no explicit source identity URL.</p>"
                b"</main></body></html>"
            ),
            redirect_count=0,
            status_code=200,
        )


def test_requested_doi_url_attests_source_identity_across_redirect() -> None:
    repository = InMemorySourceRepository()
    bundle = asyncio.run(
        ingest_public_url(
            url="https://doi.org/10.1000/VERITY.TEST",
            fetcher=RedirectedDoiFetcher(),
            repository=repository,
        )
    )

    identities = [
        item
        for item in bundle.identifiers
        if item.role == IdentifierObservationRole.SOURCE_IDENTITY
    ]
    assert len(identities) == 1
    assert identities[0].normalized_value == "10.1000/verity.test"
    assert identities[0].context_text == "https://doi.org/10.1000/VERITY.TEST"
    assert bundle.document.url == "https://publisher.example/article/verity"
    assert bundle.document.metadata["requested_url"] == "https://doi.org/10.1000/VERITY.TEST"


def test_doi_shaped_publisher_path_does_not_attest_source_identity() -> None:
    repository = InMemorySourceRepository()
    bundle = asyncio.run(
        ingest_public_url(
            url="https://publisher.example/10.1000/VERITY.TEST",
            fetcher=PublisherPathFetcher(),
            repository=repository,
        )
    )

    assert all(
        item.role != IdentifierObservationRole.SOURCE_IDENTITY
        for item in bundle.identifiers
    )
